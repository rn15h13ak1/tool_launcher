# tool_launcher

`~/ws/` 配下の各種ツールをメニュー形式で起動するランチャー。

各ツールの CLI オプションを覚えなくても、番号を選ぶだけで実行できます。

## 必要環境

- Python 3.9 以上
- ランチャー自体は標準ライブラリのみで動作します。
  `tools.yaml` でツールを追加する場合のみ PyYAML が必要です。

### セットアップ

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt    # Windows: .venv\Scripts\pip
```

`python menu.py` で使うだけなら仮想環境は不要ですが、次の場合に必要です。

- **VSCode の F5 で起動する**（`.vscode/launch.json` が `.venv` を指しているため）
- `tools.yaml` でツールを追加する（PyYAML が必要）
- テストを実行する（pytest が必要）

Homebrew や OS 同梱の Python は PEP 668 で保護されており、
`pip install` が `externally-managed-environment` で拒否されます。
仮想環境を作るのが確実です。

### 各ツールの依存ライブラリ

ツールのディレクトリに `.venv` があれば**その中の Python で実行**されるため、
ランチャー側に依存を入れる必要はありません。`.venv` が無いツールは、
ランチャーを動かしている Python で実行されます。

```bash
# .venv を用意する場合（例: file_sync_checker）
cd ../file_sync_checker
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
```

## 起動

```bash
python menu.py        # メニューを表示
python menu.py 4      # 4番のツールを直接起動（サブメニューは対話）
python menu.py --list # ツール一覧
python menu.py --log  # 直近の実行ログ
```

直接起動では**ツールの終了コードがそのまま返る**ため、バッチやタスク
スケジューラから成否を判定できます。

## 無人実行（cron / タスクスケジューラ）

ツール番号に続けてサブメニューの選択を並べると、**入力待ちなし**で実行します。

```bash
python menu.py 5 2           # ファイルリスト生成 → ドライラン
python menu.py 3 2 1         # 課題クローン → 来週 → ドライラン
python menu.py 3 2 2 --yes   # 課題クローン → 来週 → 実行（確認を承認）
```

| 状況 | 動作 |
|---|---|
| Backlog を書き換える確認 | `--yes` が無ければ**実行せずエラー終了**（exit 2） |
| 実行中のエラーで「続行しますか？」 | 無人実行では**中断**し、ツールの終了コードを返す |
| 選択が足りない / 範囲外 | エラー終了（exit 2）。何を指定すべきか表示する |
| 選択が余った | 警告を表示する（指定が実際のメニューとずれている可能性がある） |
| 日付の手動入力 | 無人実行では使用不可（週プリセットを指定する） |

**docgrep（6番）は無人実行できません。** ランチャー側にサブメニューを持たず、
docgrep 自身の対話メニューを起動するためです。自動化する場合は
`docgrep/docgrep.py` を直接呼び出してください。

`--yes` は破壊的操作を自動承認するため、**登録内容を確認したうえで**設定して
ください。ドライラン（`3 2 1` など）には不要です。

### 子ツールへの `--yes` 伝播

`excel_to_backlog` と `backlog_issue_cloner` は、非対話環境を検知すると
「確認できないのでスキップ」して**正常終了**します。そのためランチャーは、
`--yes` を付けた無人実行のときだけ子ツールにも `--yes` を渡します。

| 実行方法 | 子ツールに渡す引数 |
|---|---|
| メニューから対話実行 | `--execute`（子ツール側で1件ずつ確認する） |
| `menu.py 2 3 --yes` | `--execute --yes` |
| ドライラン | `--yes` は付けない |

これが無いと、cron から実行したときに**1件も登録されないまま成功扱い**に
なります。

## 実行ログ

実行したコマンドと終了コードを直近50件まで記録します
（`~/.tool_launcher_history.json`）。Backlog を書き換える操作を
いつ実行したか後から確認できます。

```
$ python menu.py --log
  直近の実行 2 件（新しい順）  /Users/you/.tool_launcher_history.json
--------------------------------------------------------------
    2026-08-29 10:37:07  excel_to_backlog/excel_to_backlog.py --execute   → 0
  ! 2026-08-29 10:37:06  filelist/filelist.py --dry-run   → 2
```

先頭の `!` は終了コードが 0 以外だったことを示します。

VSCode では `F5`（`.vscode/launch.json` に設定済み）でも起動できます。

前回実行したツールには `←前回` が付き、**空 Enter でそのまま再実行**できます
（履歴は `~/.tool_launcher_history.json`。ラベルで記憶するため、ツールが増減して
番号がずれても追従します）。

## メニュー一覧

| # | ラベル | 呼び出すツール | サブメニュー |
|---|---|---|---|
| 1 | Backlog 週次レポート生成 | `backlog_report/backlog_weekly_report.py` | 土〜金の週プリセット4件＋日付手動入力 |
| 2 | Excel → Backlog 課題登録 | `excel_to_backlog/excel_to_backlog.py` | ドライラン / プレビュー / 実行 / 列名一覧 / 設定名一覧 |
| 3 | Backlog 課題クローン（週次登録） | `backlog_issue_cloner/backlog_issue_cloner.py` | 今週・来週・再来週 × ドライラン / 実行 |
| 4 | ファイル同期チェック | `file_sync_checker/main.py` | 通常実行 / 詳細ログ / 再試行あり |
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
│   ├── menu.py               ← このランチャー
│   ├── tools.sample.yaml     tools.yaml のひな形
│   ├── requirements.txt      PyYAML（tools.yaml 用）
│   ├── requirements-dev.txt  pytest / pytest-cov
│   ├── pytest.ini
│   ├── tests/
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

「選択肢を選んで引数付きで実行するだけ」のツールは、**ハンドラを書かずに**
`COMMANDS` へ宣言を追加するだけで済みます。

```python
COMMANDS = [
    ...
    {
        "label":    "新しいツール名",
        "tool_dir": "new_tool",        # 未配置チェックにも使う
        "script":   "main.py",         # 省略時 main.py
        "options": [                   # 省略時は引数なしで即実行
            {"label": "通常実行", "args": []},
            {"label": "詳細ログ付き実行", "args": ["-v"]},
            # 取り消せない操作には confirm を付ける
            {"label": "実行", "args": ["--execute"],
             "confirm": "実際に書き込みます。よろしいですか？"},
        ],
    },
]
```

`confirm` を付けた選択肢は実行前に y/N を確認し、**無人実行では `--yes` が無いと
実行されません**。

日付選択のように独自の操作が必要な場合だけ、ハンドラ関数を書いて `handler`
に渡します（`Backlog 週次レポート生成` と `Backlog 課題クローン` がこの形です）。

```python
def run_new_tool():
    """新しいツール"""
    ...
    return run_script("new_tool", "main.py", args)   # 終了コードを返す
    # キャンセル時は None を返す

COMMANDS = [
    ...
    {"label": "新しいツール名", "handler": run_new_tool, "tool_dir": "new_tool"},
]
```

### `tools.yaml` で追加する（Python を書かない方法）

`menu.py` を編集せずに、同じ宣言を YAML で書けます。組み込みツールと**同じ仕組み**
で動くため、`confirm` も使えます。

```bash
cp tools.sample.yaml tools.yaml
```

```yaml
tools:
  - label: "新しいツール"
    tool_dir: "new_tool"
    script: "main.py"        # 省略時 main.py
    options:                 # 省略時は引数なしで即実行
      - {label: "通常実行", args: []}
      - {label: "詳細ログ", args: ["-v"]}
      - {label: "実行", args: ["--execute"],
         confirm: "実際に書き込みます。よろしいですか？"}
```

`tools.yaml` は起動のたびに読み直されるため、メニューを開いたまま編集しても
次の表示から反映されます。

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

## テスト

```bash
.venv/bin/pytest                              # Windows: .venv\Scripts\pytest
.venv/bin/pytest --cov=menu --cov-report=term-missing   # カバレッジ計測
```

日付ロジック、バッチ実行の制御と安全弁、各ハンドラがツールへ渡す引数、
`run_script` のガード、履歴・実行ログ、`tools.yaml` の読み込みを検証します。

`subprocess` の実行部と対話ループ（`main` / `_input_date`）は
副作用が大きいため対象外にしています。

## 終了コード

直接起動・無人実行では、**ツールが返した終了コードがそのまま返ります**。
ランチャー自身が返すのは次のコードです。

| コード | 意味 |
|---|---|
| 0 | 正常終了（メニューを終了した / ツールが 0 を返した） |
| 1 | 標準入力が閉じられた（対話の途中で EOF） |
| 2 | 引数が不正、または無人実行に必要な指定が足りない（`--yes` 不足・選択の過不足） |
| 127 | ツールのディレクトリまたはスクリプトが見つからない |
| 130 | Ctrl+C で中断 |
| その他 | 実行したツールの終了コード |

終了コード 2 は「ランチャーの使い方の誤り」と「ツールが 2 を返した」の
どちらもあり得ます。区別が必要な場合は出力メッセージを確認してください。

メニュー操作中の `Ctrl+C` は実行中のツールを中断してメニューに戻ります
（ランチャー自体は終了しません）。
