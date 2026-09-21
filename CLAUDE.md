# tool_launcher

共通規約: [../ws-conventions/README.md](../ws-conventions/README.md) に従う（`~/ws` 配下の全リポジトリ共通）。

各リポジトリ固有の事情は本ファイルに追記する。

## 共通規約からの逸脱

### `.vscode/` を丸ごとは無視しない

定型は `.vscode/` を丸ごと無視する。本リポジトリは `.vscode/launch.json` だけ追跡し、
`.vscode/settings.json` を無視する。

`launch.json` は F5 で `menu.py` を起動するための設定で、**使うインタプリタを
`.venv` に固定している。** 選択中のインタプリタ任せにすると、`tools.yaml`
（PyYAML が要る）が使えるかどうかが人によって変わるため。配りたい設定なので追跡する。
個人差が出る `settings.json` は無視したままにする。

### commit / push を確認なしで行う

定型は「利用者が明示的に指示したときだけ実行する」。本リポジトリ内の修正に限り、
利用者から包括的な指示を受けているため確認なしでコミットし、`main` へ push する
（2026-09-21）。**他のツールのリポジトリは対象外で、既定では変更しない。**

## コミット前に実行する検査

```bash
../ws-conventions/bin/check-markdown.sh .
../ws-conventions/bin/check-privacy.sh .
.venv/bin/pytest
```

ADR は使っていないため、`check-terms.sh` と `gen-decision-index.py` は対象外。
`bin/` に検査スクリプトを置いていないため、`check-commands.sh` も対象外。

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
