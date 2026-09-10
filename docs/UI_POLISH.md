# v1.2 UI Polish pass

This pass addresses the artist's Nuke runtime feedback on PR #2. The user confirmed orthogonal connections and clarified that Global had been enabled manually. The runtime version/OS of that observation was not supplied. This document does not certify a Nuke build. The PR remains Draft pending the user's next Nuke check.

## Rendering and information hierarchy

- Wire changes from `#111111` to `#929292`, with a consistent 1.15 px width for active/settled pieces. Ghost uses the same hue at alpha 105 and dashed lines. Low-alpha inter-piece contact links remain secondary.
- Filled destination arrows target 15% of cell size, bounded to 2.8-5 px and 78% of the available gap. The tip is 0.2 px before the destination edge. Geometry is strictly horizontal/vertical; rendering and endpoints share node dimensions.
- Node height increases from 46% to 56% of cell size; width stays at 78%. Class colors remain unchanged. The active outline follows the host UI highlight; settled borders remain dark; ghost nodes stay dashed outlines.
- Labels use cached fonts at 8-11 px instead of scaling paths into subpixel lettering. Full names are preferred; narrow nodes use `Xform`/`Tr`, `Gr`, `Mrg`/`Mg`, `Rd`, `Wr`, `Bl`, or `Rt`. Hover shows the full class. A 360x600 pane cannot fit Transform at a readable size without widening nodes, so abbreviation is an explicit UI tradeoff.
- Grid ON uses center dots and thin dotted guides every four moves, avoiding a square around every cell. OFF skips grid drawing. Wires remain brighter than guides.
- Normal session time appears only in STATS/Compact HUD. Score Attack remaining tenths and Sprint elapsed milliseconds appear only in the header. Challenge STATS omit time; level/lines have no zero padding.
- Next is unboxed, with 1-5 order markers in Standard and three previews in Compact. The queue stays five.
- Ranking/Settings are header tool buttons. NEW GAME stays below the board. Controls/copyright follow content, with fixed cell aspect ratio.
- Paused veil uses alpha 40/255 instead of 224/255, with a 16 px title. Ranked gameplay/competition timing is unchanged.

## Settings and location data

Settings has DISPLAY, STUDIO RANKING, GLOBAL RANKING and NETWORK sections. PRIVACY & NETWORK INFO opens a separate scrollable explanation. State text previews changes applied on SAVE; checkbox toggles alone send no Global request. Existing opt-ins are not reset.

Studio TEST explicitly checks only the selected folder's availability and reported permissions, off the UI thread. Studio OFF disables it. It neither scans contents nor writes score/test files. Folder changes, disabling or closing discard stale results and cancel subsequent work. An already running OS call can wait on an unavailable NAS. Available/Read only does not certify actual NAS write/lock/replace semantics.

All existing country codes have bundled English labels. Japan has 47 prefectures, `JP-01` through `JP-47`. Other countries use optional validated region text. Blank optional regions use `-`, already accepted by the protocol; the UI omits that marker. No API fields or settings schema are added.

Legacy `TOKYO`, `SAITAMA`, and `JP-13` show readable labels. Unchanged legacy values survive save and switching countries/back. New prefecture selections use JP codes. Unknown saved regions remain selectable. Invalid edits/save failures leave prior settings intact. Round-trip tests cover credentials, PBs, folder, identity and enable flags. Ranking AREA also uses readable labels.

Country names are static Unicode CLDR data; its Unicode-3.0 notice is embedded in `src/locations.py` and the generated file. No runtime downloads, locale detection, geolocation or new installed dependencies are used.

## Reported board badge

The white NUKERIS badge has not been reproduced. Starting `20fb8d3` sources and generated file have no board badge/watermark drawing; NUKERIS is painted in the header only. The default local installation path had no separate installed file to compare. The user was asked for the loaded path and whether the badge appears only on hover.

The rendering test asserts no NUKERIS title is painted within the board. Panel tooltip handling exposes node-class labels, not branding. No arbitrary host widgets were hidden/deleted to mask an unidentified source. **The original badge still needs confirmation in the user's Nuke session; do not report its source as fixed.**

## Verification and manual follow-up

Run pure Python, Qt smoke/polish/transport, backend, build and whitespace checks. Qt checks timer placement, formatting, fresh/saved opt-ins, no network manager during import/open, Studio-off prevention, locations/country switching, settings round trips/failures, matching node/wire edges, badge absence in our painting, pause visibility and Standard/Compact/Tall navigation. Screenshots use deterministic test state, a fake Nuke module and temporary settings; they are not Nuke screenshots.

The user should recheck fonts/DPI, both wire directions/arrows, labels/hover names, Grid ON/OFF, pause, Normal timer duplication, Challenge clocks, pane sizes, Settings/locations/navigation, disabled-network/share behavior and Node Graph/Viewer/Timeline/Undo isolation. Global remains undeployed/unconfigured. No new modes or ranking features are added.

## References checked

- [Foundry: Working with Nodes / Connecting Nodes](https://learn.foundry.com/nuke/content/getting_started/using_interface/working_nodes.html) — connection/arrow terminology and appearance; pixel adjustments above are NUKERIS choices, not claimed Foundry metrics.
- [Unicode CLDR English territories](https://github.com/unicode-org/cldr-json/blob/main/cldr-json/cldr-localenames-full/main/en/territories.json) — country display names, retrieved 2026-09-11.
- [Statistics Bureau of Japan census summary](https://www.stat.go.jp/english/data/kokusei/2020/summary/pdf/all.pdf) — prefecture names/order.
- [ISO 3166 country codes](https://www.iso.org/iso-3166-country-codes.html) — country/subdivision coding context.
