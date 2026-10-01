# tool_launcher

共通規約: [../ws-conventions/README.md](../ws-conventions/README.md) に従う（`~/ws` 配下の全リポジトリ共通）。

各リポジトリ固有の事情は本ファイルに追記する。

## 共通規約からの逸脱

### commit / push を確認なしで行う

定型は「利用者が明示的に指示したときだけ実行する」。本リポジトリ内の修正に限り、
利用者から包括的な指示を受けているため確認なしでコミットし、`main` へ push する
（2026-09-21）。**他のツールのリポジトリは対象外で、既定では変更しない。**

## テストの置き場と実行

[Python のテストの手引き](../ws-conventions/guides/python-test.md)の標準に合わせている。
`pytest.ini` の `pythonpath = .` で import を通すため、**テストファイル側に
`sys.path` を書かない**（書くとファイルが増えるたびに写すことになる）。

## コミット前に実行する検査

```bash
../ws-conventions/bin/check-markdown.sh .
../ws-conventions/bin/check-privacy.sh .
.venv/bin/python -m pytest
```

ADR は使っていないため、`check-terms.sh` と `gen-decision-index.py` は対象外。
`bin/` に検査スクリプトを置いていないため、`check-commands.sh` も対象外。

## 画面に出す文字は CP932 に収める

Windows の日本語コンソールは既定で CP932 になる。CP932 に無い文字を `print` すると
文字化けではなく `UnicodeEncodeError` で落ち、`menu.bat` のダブルクリックでは
**最初の画面すら出ない。** 開発機が macOS だと気付けないため、
`tests/test_windows.py` で固定している。

`✓` `✗` `⏳` や em dash（`—`）は使えない。`←` `※` `〜` `─` `→` 全角スペースは使える。

**ソースの検査だけでは足りない。** `tools.yaml` のラベルは利用者が書くため、検査で
防げない。`main()` の冒頭で `make_console_safe()` を呼び、UTF-8 でないコンソールに
限って表せない文字を `?` に置き換えている。**入口の呼び出しを外すと、絵文字を 1 つ
書かれただけでメニューの一覧表示で落ちる。**

## メニュー番号を変えない

`README.md` は `menu.py 3 2 1` のような無人実行コマンドを cron 用に案内している。
**選択肢は末尾に足す。** 途中に挿入すると、利用者が登録済みのコマンドの意味が
黙って変わる。番号の並びはテストで固定している
（`test_menu_order_is_stable` / `test_cloner_week_numbers_are_unchanged`）。

## ツール側にメニューがある場合は委譲する

`script` に `menu.py` を指定すると、ランチャーはサブメニューを持たずツール側の
対話メニューをそのまま起動する。オプションの追加はツール側だけで完結する。

例外は Backlog 課題クローンの週次一括登録で、ツール側のメニューが 1 日ぶんしか
扱わないためランチャー側に残している。
