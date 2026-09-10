# Verification and manual testing

## Automated checks

- `python tools/build.py --check`: the single-file distribution matches all development sources.
- `python -m unittest discover -s tests -v`: Qt/Nuke-free engine, storage, migration, timing, geometry, Studio, Global protocol and privacy regressions.
- `node --test backend/test/worker.test.mjs`: Worker handler and SQL with an in-memory SQLite D1 adapter; not a live Cloudflare deployment.
- `python tests/run_qt.py`: offscreen widget construction/paint/resize/dialogs, offline initialization, modified keys and Esc during an online start, stale start-reply rejection, and real Qt transport with fake replies (success, malformed JSON, redirects, oversized data, timeout).
- `git diff --check`: patch whitespace validation.

The Normal trace fixture was captured from v1.1.0 `f12d176` using an explicit fixed queue. It checks movement/rotation/drop/hold/top-out state and score parity rather than relying on the new implementation to invent its own expected values.

## Local evidence during implementation

Windows: Python 3.12.14, Node 24.19.0, isolated PySide6 6.8.3. Pure Python tests, backend tests and Qt smoke/transport checks pass. Standard/Compact and both dialogs were rendered offscreen and visually inspected. This is **not Nuke runtime verification**. No installed Nuke was launched and no user's comp/settings were used.

Local Python 2.7 and PySide2 runtimes were unavailable. The Windows Python 2 replacement path was exercised using the fallback under Python 3, which is not the same as running Python 2.7. CI is configured for actual Python 2.7.18 on Linux, Python 3.11/3.12 on Windows/Linux, PySide2 5.15.2.1 and PySide6 6.5.3 on Windows/Linux, plus backend tests. Consult the PR checks for current outcomes; configuration alone is not success evidence.

## CI evidence

On 2026-09-10, [run 34478506090](https://github.com/MoriKouta/NUKERIS/actions/runs/34478506090) at `f1a6649` passed all ten jobs:

| Environment | Executed checks | Result |
| --- | --- | --- |
| Linux container, Python 2.7.18 | Distribution syntax/build and 45 pure Python tests | PASS |
| Ubuntu 22.04 / Windows runner, Python 3.11 and 3.12 | Distribution syntax/build and 45 pure Python tests per combination | PASS |
| Ubuntu 22.04 / Windows runner, Python 3.9, PySide2 5.15.2.1 | Offscreen UI and Qt transport checks | PASS |
| Ubuntu 22.04 / Windows runner, Python 3.9, PySide6 6.5.3 | Offscreen UI and Qt transport checks | PASS |
| Ubuntu 22.04, Node 24 | 11 Worker/SQLite adapter tests | PASS |

The first run failed because the test's header getter used a newer Qt signature and the Linux runner lacked EGL. Both CI/test issues were corrected. Later commits add the pending-start input regression above; consult [Draft PR #2 checks](https://github.com/MoriKouta/NUKERIS/pull/2/checks) for the current revision. These results do not certify Nuke's embedded Qt builds or Python 2.7 on Windows.

## Required manual Nuke checks

Record exact Nuke version, OS, Python and PySide for every checked environment. The target matrix remains Nuke/NukeX 12–17 on Windows/Linux. A test on one version does not certify another.

1. Startup/menu registration and panel open, dock/float, workspace restore and panel recreation.
2. Verify no comp dirty-state change, node/knob/Viewer/frame/timeline/Undo changes, or project/asset information collection. Do not modify a user's current comp to perform the check.
3. Hold/Next/Ghost, left/right movement, all rotations/wall kicks, soft/hard drop, line clears, combo/level, game over and Normal PB persistence.
4. Focus loss, Esc, modifiers, focus on other Nuke panes, hidden tabs and close/reopen. Confirm no Nuke single-key shortcut fires during game input and normal shortcuts work after input release.
5. Standard/Compact sizes, minimum size, high DPI, different Nuke fonts/palettes, readable labels and horizontal/vertical edge-connected arrows. Resize during play without state loss.
6. Score Attack boundary at 2:00, ten-second accent, pause/focus loss beyond deadline. Sprint's exact completion and millisecond time, including final multi-line overshoot and failed runs.
7. Legacy settings migration with missing/corrupt/read-only source; user-path Unicode; unwritable destination; two panels/processes; no PB decrease or old-file deletion.
8. Initial install/import/open and saved-off preferences with no network or share access. Saved-on preferences still must not send requests merely from opening.
9. Studio empty/valid/corrupt/mixed files, share disconnect, permission denial, two writers, disable during pending work and closing Nuke during an unavailable-share operation. Verify actual NAS lock/rename behavior.
10. After separate deployment approval: Global registration/profile updates, signed run start, Score Attack/Sprint submission, duplicate rejection, world/country/region ranks and empty board. Test timeout, TLS failure, malformed response and turning off with in-flight requests; Personal PB must remain.

## Limits of the current tests

No actual Nuke GUI/comp test, real SMB/NFS mount test, production Cloudflare/D1 deployment, billing/account setup or end-to-end public HTTPS ranking test was performed. Fake HTTP replies and SQLite validate client/handler behavior without proving platform deployment or transport availability. Power-loss and filesystem administrator attacks are not covered.
