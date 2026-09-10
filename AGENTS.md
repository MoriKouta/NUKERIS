# AGENTS.md — NUKERIS 開発ルール

このファイルはリポジトリ全体の開発ルールです。v1.2 は Issue #1、`ai/1-v1.2-arcade-update` で実装します。

## 対象と基本方針

- 対象は GitHub `MoriKouta/NUKERIS`。Nuke 内で動作する、comp から隔離した落ち物パズルの継続開発を行う。
- ユーザーの依頼範囲を守る。調査依頼を実装・commit・push の許可に読み替えない。
- 作業前に `git status --short --branch`、現在の branch、remote、関連 Issue／PR、差分を確認する。
- ユーザーの未commit変更・未追跡ファイルを保護する。reset、変更を失う checkout／restore、overwrite、削除を行わない。作業が衝突する場合は、変更を保持して対象と必要な判断を報告する。
- サブエージェント利用の可否はユーザーの指示に従う。

## 恒久ルール

1. main へ直接 push しない。
2. 作業ごとに Issue を確認し、専用 branch を使う。
3. commit 前に可能な tests を実行する。
4. Nuke の current comp へ干渉しない。
5. .nk script、Node、Knob、Viewer、Timeline、current frame、Undo stack を変更しない。
6. Read / Write path や Project 情報を不要に取得しない。
7. Offline by default を維持する。
8. Telemetry、Analytics、LAN scan、listening port、background service を勝手に追加しない。
9. PySide2 / PySide6 互換性を維持する。
10. Nuke 12〜17、Windows / Linux の既存 support を勝手に削除しない。
11. Python 2.7 support が問題になる場合は、勝手に切らず報告する。
12. Credential や secret を Repository へ commit しない。
13. Nuke 実機で確認していないものを「確認済み」と扱わない。
14. 既存機能の regression を避ける。
15. 大きな変更は意味のある単位で commit を分ける。

## Git とレビュー

- 専用 branch は、特別な指定がなければ `codex/<issue-number-or-topic>` を使う。main への反映は PR 経由とする。
- 対応する Issue がない場合は、その事実と作業範囲を整理する。調査のみの依頼では Issue／PR 作成や branch 切り替えを勝手に行わない。
- 個別ファイルを選んで stage し、commit 前に staged diff と生成物・設定・credential の混入を確認する。
- 該当する tests と `git diff --check` を実行し、結果・未実施項目・理由を報告する。
- 古い開発 branch、release tag、配布 ZIP の内容が現在の main と同じとは限らない。移植や配布の前に差分と対象 commit を確認する。

## コード構成と責務

2026-09-10 に確認した基準は v1.1.0、commit `f12d1769268468ed729f02601fef80759984f367`。将来の作業では現在の実ファイルを優先する。

- 配布用コードは `nukeris.py` の単一ファイル。既存の `.nuke` への配置と `menu.py` からの import を保つ。
- `_enum_value` と `QC`：Qt5／Qt6 の enum 差を吸収する。現在の import は PySide6 を試してから PySide2 に fallback する。
- `Tetromino`／`PlacedCell`：ピース位置・回転と固定セルのデータ。
- `GameEngine`：10×20 の盤面、7-bag、移動、SRS 回転、Hold、Next、Ghost、落下、固定、行消去、score／combo／level。
- `NukerisPanel`：Qt widget、入力と focus、開始／pause、QTimer、レイアウト、描画。
- `paintEvent` と `_draw_*`：QPainter によるノード風の装飾。ゲーム上の Read／Write 等は文字・図形であり、Nuke Node ではない。
- `_settings_path`／`_load_best_score`／`_save_best_score`：モジュール隣の `nukeris_settings.json` の `best_score` を扱う。保存途中には `.tmp` も使う。
- `register_panel`：GUI 時に Pane メニューへ登録する。module import の末尾で呼び出される。
- GameEngine の処理は Qt／Nuke API を直接使わないが、現状は設定 I/O を呼び、ファイル全体の import には Qt が必要。完全に副作用のない単独 import 可能な engine として扱わない。

## 安全設計の維持

- Nuke API との接点は GUI 判定とパネル登録に限定する。comp 調査、Node／Knob 操作、Viewer 操作、frame 変更、Undo 操作を追加しない。
- キーボード処理はパネルの focus 内に限定する。Nuke のショートカット設定を変更せず、global shortcut／global event filter を追加しない。
- focus 喪失・非表示・pause・game over でゲーム timer を止める。Esc の入力解放を維持する。
- ゲーム更新・入力・描画での例外を安全な停止へ導き、Nuke 起動や通常操作への影響を抑える。
- アプリ全体の palette、font、乱数 generator、環境変数等の共有状態へ新たな副作用を追加しない。現行コードの共通 random 利用は改善検討事項として扱う。
- 設定に保存するのはゲームに必要な値だけ。comp 情報、素材 path、credential を保存しない。
- 設定保存変更では、旧データの保持、書込不可、破損 JSON、複数パネル／複数プロセス、共有インストール先を考慮する。
- 設定・一時ファイルを新しく作成する tests は一時領域と分離した I/O を使い、利用中の設定や current comp を変更しない。

## 互換性と検証

維持する target は以下。表は support 方針であり、実機確認済み一覧ではない。

| Nuke | Python | Qt binding | OS |
| --- | --- | --- | --- |
| 12.x | 2.7 | PySide2 | Windows / Linux |
| 13.x〜15.x | 3 | PySide2 | Windows / Linux |
| 16.x〜17.x | 3 | PySide6 | Windows / Linux |

- Python 2.7 が構文解析できない f-string、関数 annotation、async 構文等を配布ファイルへ導入しない。新しい標準ライブラリ API には対応 target で動く fallback を用意する。
- UTF-8 宣言、Unicode、除算、単調時計の fallback、Qt enum と描画 API の違いを考慮する。
- Qt binding の import 成功や構文検査成功だけで Nuke／OS の動作確認済みと判定しない。
- 現在の CI は `.github/workflows/compatibility.yml`。Python 3.11 と Docker の Python 2.7 で `nukeris.py` と存在する `nukeris_dev_*.py` の構文を確認する。
- 2026-09-10 の基準では専用 tests ディレクトリと engine／settings／UI の自動 regression tests はない。存在しないテストを実行済みと報告しない。
- engine や settings の挙動変更には変更リスクに対応する分離 tests を用意する。UI のみの軽微な変更は必要な表示・操作確認を選ぶ。
- UI／入力変更では両 binding、dock／float、focus 喪失、Esc、modifier 付きキー、非表示、再表示、panel 再作成を対象に検証する。
- 実機検証の記録には Nuke の完全な version、OS、Python、PySide、検証項目と結果を残す。未実施は明記する。

## 調査で見つかった未解決事項

- settings 保存は固定 `.tmp` と remove＋rename であり、atomic な置換ではない。rename 失敗時の旧データ消失と複数 instance の score 後退を分離検証で再現した。
- ゲームは module-level `random.shuffle` を使い、Nuke プロセス内の他の Python 処理と乱数状態を共有する。
- `keyPressEvent` 自体には Ctrl／Alt／Meta 判定がないため、ShortcutOverride に任せた modifier の扱いを実機で確認する。
- `.gitignore` は Python cache と OS 雑ファイルのみを除外し、settings／`.tmp`／`.env` 等は除外していない。
- branch 保護、Issue／PR、CI の状態は変化するため、必要時に GitHub の現状を読み直す。
- これらは調査所見であり、この文書の採用だけで修正や v1.2 実装を開始する許可にはならない。v1.2 は仕様・受入条件・対象 Issue が明確な依頼を受けてから着手する。

## 報告

- 日本語の自然な敬語で回答し、一人称は「私」に統一する。
- 最新性の関係する情報は Web で確認し、公式ドキュメント等の一次情報を優先して出典を明記する。
- 実コードの確認、構文検査、分離した模擬検証、Qt 単体検証、Nuke 実機検証を区別する。
- Nuke／Python の納品は完成形とし、長いものは取得可能なファイル、短いものはコピー可能な形にする。
- 判断に必要な仕様や関連ファイルが不足している場合は、必要なものを具体的に伝える。

## v1.2 の明示的な作業範囲と開発構成

- 今回はユーザーの依頼により実装・tests・commit・feature branch push・Draft PR 作成まで実施する。サブエージェントは使用しない。
- `src/core.py` と追加の純粋 Python source を Qt なしでテストする。`src/ui.py` は Qt UI。`tools/build.py` が単体配布用 `nukeris.py` を生成する。生成物を直接編集しない。
- `python tools/build.py --check`、`python -m unittest discover -s tests -v`、`git diff --check` を実行する。
- Studio は明示設定した shared folder のみ、Global は明示 opt-in 後の必要時だけ非同期 HTTPS を許可する。No Telemetry / No Analytics / No LAN Scan / No Listening Port / No Background Service。
- ランキングの on-demand I/O worker は必要な操作だけ実行して終了する。常駐 service や常時 polling を作らない。
- Ranked の competition clock は focus 喪失・pause 中も経過する。gameplay timer は停止し、再表示時に期限を再評価する。
- Global の server-issued player token は個人の設定にのみ保存し、repository・log・公開ランキングには含めない。comp や host の情報は取得・送信しない。
- Cloudflare backend source と local tests は作成するが、本番 deploy、D1 本番作成、secret 設定、domain／DNS／billing 変更は行わない。
- 上記の調査時点の構成・未解決事項は baseline の説明であり、変更後の実装を優先する。
