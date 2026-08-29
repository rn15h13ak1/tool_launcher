# tool_launcher

`~/ws/` 配下の各種ツールをメニュー形式で起動するランチャー。

各ツールの CLI オプションを覚えなくても、番号を選ぶだけで実行できます。

## 必要環境

- Python 3.9 以上
- 各ツール自身の依存ライブラリ（`PyYAML` / `openpyxl` / `tqdm` など）は、
  このランチャーを動かす Python 環境にインストールしておく必要があります。

## 起動

```bash
python menu.py        # メニューを表示
python menu.py 6      # 6番のツールを直接起動
```

VSCode では `F5`（`.vscode/launch.json` に設定済み）でも起動できます。

## メニュー一覧

| # | ラベル | 呼び出すツール | サブメニュー |
|---|---|---|---|
| 1 | Backlog 週次レポート生成 | `backlog_report/backlog_weekly_report.py` | 土〜金の週プリセット4件＋日付手動入力 |
| 2 | Excel → Backlog 課題登録 | `excel_to_backlog/excel_to_backlog.py` | ドライラン / プレビュー / 実行 |
| 3 | Backlog 課題クローン（週次登録） | `backlog_issue_cloner/backlog_issue_cloner.py` | 今週・来週・再来週 × ドライラン / 実行 |
| 4 | ファイル同期チェック | `file_sync_checker/main.py` | 通常実行 / 詳細ログ |
| 5 | ファイルリスト生成 | `filelist/filelist.py` | 通常実行 / ドライラン / 詳細ログ |
| 6 | docgrep（ファイル全文検索） | `docgrep/menu.py` | docgrep 側の対話メニューに委譲 |

### 3. Backlog 課題クローンの日付ルール

選択した週の月〜金を1日ずつ処理します。**今週を選んだ場合、当日以前はスキップ**され、
翌日以降の日付だけが登録対象になります。来週・再来週は5日分すべてが対象です。

## ディレクトリ構成

ツールは `menu.py` から見て**ひとつ上の階層**に並んでいる前提です。

```
ws/
├── tool_launcher/
│   ├── menu.py          ← このランチャー
│   └── .vscode/launch.json
├── backlog_report/
├── excel_to_backlog/
├── backlog_issue_cloner/
├── file_sync_checker/
├── filelist/
└── docgrep/
```

ツールが配置されていない場合、メニューには `※未配置` と表示され、
選択してもランチャーは落ちずにメッセージを出してメニューに戻ります。

## 新しいツールを追加する

1. ハンドラ関数を定義する
2. `COMMANDS` リストにエントリを追加する

```python
def run_new_tool():
    """新しいツール"""
    options = ["通常実行", "詳細ログ付き実行"]
    choice = print_menu("新しいツール", options)
    if choice == 0:
        return
    args = ["-v"] if choice == 2 else []
    run_script("new_tool", "main.py", args)


COMMANDS = [
    ...
    {
        "label":    "新しいツール名",
        "handler":  run_new_tool,
        "tool_dir": "new_tool",     # 未配置チェックに使用
    },
]
```

### `run_script()` の使い方

```python
rc = run_script(tool_dir_name, script_name, args=None, wait=True)
```

| 引数 | 説明 |
|---|---|
| `tool_dir_name` | `ws/` 配下のディレクトリ名 |
| `script_name` | 実行する Python スクリプト名 |
| `args` | コマンドライン引数のリスト |
| `wait` | `False` にすると終了後の Enter 待ちをスキップ（連続実行用） |

戻り値は子プロセスの終了コード。ツールやスクリプトが見つからない場合は
`127` を返し、例外は投げません。

## 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常終了 |
| 1 | 直接起動時に標準入力が閉じられた |
| 2 | 直接起動時の引数が不正 |
| 130 | 直接起動時に Ctrl+C で中断 |

メニュー操作中の `Ctrl+C` は実行中のツールを中断してメニューに戻ります
（ランチャー自体は終了しません）。
