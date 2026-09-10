# NUKERIS v1.2 architecture

`nukeris.py` remains the single-file distribution. Edit sources and run `python tools/build.py`; do not hand-edit the generated file. The build only reads local sources and writes the distribution. It embeds the storage primitives into the core, then geometry, modes, settings, Studio and Global protocol code, then the Qt adapter/dialogs/panel.

| Source | Responsibility |
| --- | --- |
| src/core.py | Tetromino data, SRS, 7-bag, engine, isolated seeded RNG |
| src/storage.py | Bounded JSON reader, unique temporary writes, OS locks, safe replacement |
| src/geometry.py | Orthogonal edge endpoints and responsive board layout |
| src/modes.py | Session clocks, completion, result records, mode/ruleset IDs |
| src/settings.py | User settings v2, legacy migration, local PB merging and pending results |
| src/locations.py | Static country/prefecture display data and legacy label conversion |
| src/studio.py | Explicit shared-folder access and validated per-player PB files |
| src/global_client.py | Opt-in protocol, payload allowlist and response validation; no HTTP library |
| src/network.py | Lazy QtNetwork transport with timeout, size bound and cancellation |
| src/dialogs.py | Ranking UI and on-demand Studio I/O |
| src/settings_ui.py | Settings/privacy dialogs, location selectors and explicit folder test |
| src/ui.py | Nuke-looking widget, gameplay focus, timers, rendering and panel registration |
| backend/ | Worker API, D1 schema and tests using an in-memory SQLite adapter |

The pure Python test suite builds the same source used for distribution without the Qt portion. It does not import Nuke or Qt. Normal engine behavior is additionally compared with a frozen trace captured from v1.1.0 commit `f12d176` using an explicit piece queue.

## Ruleset 1

Modes are `normal`, `score_attack_120`, and `sprint_40`. Only the latter two use shared rankings; all ranked records carry `ruleset_1` and the NUKERIS version. Ruleset-changing updates must create a new ID rather than mixing incompatible records.

Normal retains v1.1 scoring: line awards 100/300/500/800 multiplied by the level after the clear; successive clear combo adds 50 × combo × level. Level is 1 + total lines // 10. Soft drop awards 1 per cell and hard drop 2 per cell. Gravity is max(70, int(760 × .82 ** (level - 1))) milliseconds; collision locks immediately, with the existing SRS kick tables and seven-bag. Sorting the initial bag gives seeded reproducibility across Python versions; the uniform seven-bag rule is unchanged.

Score Attack ends at 120,000 ms or top-out; top-out may yield an earlier result. Sprint succeeds at 40–43 lines (a final multiple-line clear may overshoot); top-out before 40 is not a ranking result. Sprint stores elapsed integer milliseconds and sorts ascending. Score Attack sorts score descending. Equal scores/times share the same competition rank; display ordering is stable.

Normal active time advances only on gameplay ticks with the existing delta clamp. Ranked elapsed time is derived from a clock independent of gameplay ticks. Focus loss, manual pause and hiding stop gameplay; the ranked deadline continues elapsing. The next input/timer/show/focus event evaluates the deadline before allowing more moves. Hidden panels do not poll. Python 2.7 uses the wall-clock fallback with non-decreasing elapsed values; this does not provide trusted anti-cheat timing.

## Persistence

`~/.nuke/NUKERIS/settings.json` stores schema 2, Normal PB, ranked PBs keyed by mode/ruleset, UI choices, explicit ranking opt-ins, Studio path/identity and the online profile/credentials. Both ranking opt-ins default to false. A legacy `nukeris_settings.json` beside the loaded distribution is read for Normal PB migration and never deleted.

Writes acquire a nonblocking OS sidecar lock, read the latest data, merge PBs in the correct direction, write a unique same-directory temporary file, flush/fsync/close, and replace. Python 3 uses `os.replace`; Python 2.7 Windows uses `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)` and POSIX uses atomic `rename`. If replacement is unavailable, the operation fails while preserving the old final file. It never removes the final file first. Locks release when the handle closes. A busy/unavailable store fails safely rather than waiting for lock ownership in the UI.

Local save failure retains pending PBs in memory for a later save attempt. This cannot guarantee persistence after process exit when the disk is unwritable. Newer unknown schemas are not overwritten. Studio and Global failures never roll back or delete personal results.

Studio writes one `scores/<mode>/ruleset_1/<32-hex-player-id>.json` PB per player, with no credential data and no shared giant leaderboard. Readers ignore temp files, malformed/oversized JSON, schema/ruleset mismatches, filename/identity mismatches, symlinks, invalid profiles and impossible results. Only the selected root and the chosen mode/ruleset directory are considered. Root creation is the studio operator's responsibility.

Studio operations run only on demand, in at most two transient worker threads, to keep remote filesystem waits off the GUI. No server, daemon process, timer polling or long-running service is installed. Disabling ranking invalidates queued work; an OS filesystem operation already in progress cannot be forcibly cancelled. Actual NAS latency, locking and rename guarantees must be checked on the target share.

## Global protocol

The public endpoint constant is intentionally empty until an approved deployment exists. `QNetworkAccessManager` is created on the first eligible user action, not on import/open or opt-in alone. Requests have a ten-second abort timer, a 128 KiB response ceiling, no automatic redirects, no automatic cookies/authentication reuse, no system proxy discovery and no TLS error bypass. Results save locally before optional submission.

- `POST /v1/players`: manually entered profile → server-issued random ID/token; only SHA-256 token hashes are stored server-side.
- `POST /v1/profile`: explicit profile update using the player token.
- `POST /v1/runs`: authenticated mode/ruleset/version → signed run token and seed, requested before starting a Global run.
- `POST /v1/results`: signed token and allowlisted result; sanity, timing, identity/version/ruleset validation; transactional duplicate rejection and PB update.
- `GET /v1/leaderboard`: global top 100 plus the authenticated player's world/country/region ranks, without user totals.

Global failure at start falls back to a local run with a visible status. Failed submission leaves the personal PB intact; old local PBs are not uploaded as if they had server-issued run tokens. No automatic retry loop or polling is used. Public profile creation/update and ranking refresh require explicit actions.
