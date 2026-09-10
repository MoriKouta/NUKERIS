# NUKERIS v1.2 — Arcade Update

A Nuke-native falling-block puzzle game for quick breaks while compositing.

## Security / Privacy

**NUKERIS is fully offline by default.**

Installing or opening NUKERIS does not initiate network connections.

Online Ranking is opt-in. Global and Studio ranking are both OFF initially.

No telemetry. No analytics. No LAN discovery. No listening ports. No background services.

NUKERIS does not read or transmit Nuke scripts, node data, paths, project data or Foundry account information. It does not modify nodes, knobs, Viewer, timeline, current frame or the Undo stack.

Studio Ranking only accesses the explicitly configured shared folder. Existing OS permissions are used; no NAS credentials are stored. Global requests use asynchronous HTTPS only for explicit ranking actions and opted-in runs. Enabling Global alone does not send a request.

The Global backend is implemented but **not deployed** in this update branch. No official endpoint is configured yet; Personal and Studio ranking work independently of it. See [backend setup and human actions](backend/README.md) and [security details](docs/SECURITY.md).

## Arcade modes

| Mode | Goal | Pause / focus loss | Ranking |
| --- | --- | --- | --- |
| NORMAL | Unlimited, v1.1 gameplay | Gameplay and session time pause | Local best score only |
| SCORE ATTACK — 2:00 | Highest score in 120 seconds | Gameplay pauses; competition time continues | Higher score wins |
| 40 LINE SPRINT | Clear 40 lines as quickly as possible | Gameplay pauses; competition time continues | Lower time_ms wins |

Sprint displays milliseconds. Ranked results carry `ruleset_1`. A failed Sprint has no ranking result. Score Attack ends at the deadline or top-out. The final Sprint clear may reach 40–43 lines. The last ten seconds of Score Attack use a restrained warning accent.

Hidden panels stop gameplay timers. Ranked elapsed time is computed independently and checked before the next move or on returning to the panel. A long-hidden finished Global run may miss the server submission window; its Personal result remains independent.

## Nuke-style UI

- Read / Merge / Transform / Roto / Grade / Blur / Write mappings and base colors are retained.
- Orthogonal edge-to-edge wires and small filled destination arrows; ghost wires use low opacity and dashes.
- STANDARD: HOLD | BOARD | NEXT. COMPACT: HOLD/NEXT above the board, HUD below it.
- Five Next previews in Standard, three in Compact; the engine still exposes a five-piece Next queue.
- Hold, Next, Ghost, SRS wall kicks, combo, level progression, line-clear effects and optional Node Graph grid.
- Thin highlights, subtle shadows, restrained controls and focus-based keyboard ownership.
- Resizing does not recreate game state.

The UI Polish pass improves wire/arrow contrast and node height, removes Next preview boxes and keeps Ranking/Settings in the header. Narrow nodes use readable abbreviations with full names on hover. Normal time appears only in STATS; challenge clocks appear only in the header. Grid uses dots/sparse guides, and paused boards stay visible. See [polish details and remaining runtime checks](docs/UI_POLISH.md).

## Installation

1. Copy the generated **nukeris.py** into your `.nuke` folder.
2. Add `import nukeris` to your existing `menu.py`.
3. Restart Nuke and open **Pane → NUKERIS**.

Windows: `C:\Users\<USER>\.nuke\nukeris.py`

Linux: `~/.nuke/nukeris.py`

No supporting source folders or third-party Python packages need to be installed in Nuke. For an existing subfolder setup, keep its plugin path and import arrangement unchanged.

## Controls

| Key / control | Action |
| --- | --- |
| A / D, Left / Right | Move |
| S, Down | Soft drop |
| Q / E, Up | Rotate |
| C | Hold |
| Space / W | Hard drop |
| Esc | Pause and release input; cancel a pending Global start |
| Space / Enter while ready or paused | Start / resume |
| Mode selector + NEW GAME | Start selected mode |
| RANKING / SETTINGS | Open local dialogs; gameplay pauses |

Keys are handled only while the game widget owns focus. Ctrl/Alt/Meta combinations are left to Nuke. Ranked pause displays **Ranked timer is still running.**

## Settings v2 and Personal Ranking

Settings are stored at `~/.nuke/NUKERIS/settings.json`, including Normal PB, per-mode/ruleset ranked PBs, grid preference and ranking opt-ins. Legacy `nukeris_settings.json` beside the loaded module is migrated without deleting the old file. The highest Normal PB is preserved.

SETTINGS separates Display, Studio, Global and Network state. PRIVACY & NETWORK INFO opens detailed safety information. Countries have readable names; Japan has a 47-prefecture selector. Other countries allow optional validated region text. Existing profile values and opt-ins are retained until changed. Studio TEST checks only the selected folder's availability/reported permissions after explicit enablement; it neither writes files nor certifies all NAS guarantees.

Unique temporary files, flush/fsync/close, OS locks and safe replacement protect saved data. If local persistence fails, the previous file is retained and new records remain in memory for a later save attempt. An unwritable disk cannot preserve those pending changes across process exit. Studio/Global failures never delete Personal results.

## Studio Shared Folder Ranking

Choose SETTINGS, enter the absolute shared folder path and a public nickname/country/region, then explicitly enable Studio. The root must already exist. Example paths: `\\server\tools\nukeris-ranking` or `/mnt/studio/tools/nukeris-ranking`.

```text
nukeris-ranking/
    studio.json                 # optional operator description; no credentials
    scores/
        score_attack_120/
            ruleset_1/
                <player-id>.json
        sprint_40/
            ruleset_1/
                <player-id>.json
```

Only PBs are saved, one file per player/mode/ruleset. A nickname is a display label, not an authentication identity. This is trust-based friendly competition. Invalid/partial/temp/mismatched records are ignored. The selected folder is accessed only after opt-in; no network discovery or server process is used. An already dispatched OS filesystem operation may finish after disabling Studio, while queued/new operations are cancelled.

RANKING → STUDIO → REFRESH reads that board once. Missing/disconnected/read-only shares do not prevent local play. Actual NAS rename/locking behavior needs validation by the studio.

## Global Ranking

After an approved backend is configured, enable Global explicitly and use RANKING → GLOBAL → CREATE / UPDATE ONLINE PROFILE. Nicknames allow 2–16 characters: A–Z, a–z, 0–9, `_`, `-`, `.`. Choose country manually and enter a region/prefecture manually; no location lookup occurs.

Starting a challenge requests a signed run token and seed, then starts the clock. Completed eligible results save locally before optional submission. Ranking shows the global top 100 and YOUR RANK at WORLD / COUNTRY / REGION level. Empty boards show **NO SCORES YET — Set the first record.** No fake scores, bot users or constant user totals are included.

No email, password or Foundry account is required. A server-issued bearer token is stored only in the user's local settings; never share that file. The server stores its hash. Network timeouts, TLS errors, malformed responses and service failures leave local results intact. There is no polling or automatic retry loop. Offline records are not later uploaded as if they were signed Global runs.

## Compatibility and development

| Nuke | Python | Qt binding | OS targets |
| --- | --- | --- | --- |
| 12.x | 2.7 | PySide2 | Windows / Linux |
| 13.x–15.x | 3 | PySide2 | Windows / Linux |
| 16.x–17.x | 3 | PySide6 | Windows / Linux |

These are maintained support targets, not a claim that all Nuke releases have been tested. See [actual verification and manual checklist](docs/TESTING.md).

```sh
python tools/build.py
python tools/build.py --check
python -m unittest discover -s tests -v
node --test backend/test/worker.test.mjs
```

With PySide2 or PySide6 installed in a separate test Python environment, `python tests/run_qt.py` runs offscreen Qt tests using a fake Nuke module and temporary settings. It never starts Nuke. See [architecture and ruleset details](docs/ARCHITECTURE.md) and [development rules](AGENTS.md).

Daily/Weekly challenges, achievements, replay, ghost rivals, friends/chat, email/social login, Studio servers/discovery, department rankings and automatic geolocation are outside this release.

## License

MIT — [LICENSE](LICENSE). © 2026 Kota Mori.
