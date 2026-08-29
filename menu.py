#!/usr/bin/env python3
"""
Tool Launcher - メニュー形式のツール起動スクリプト
================================================
Windows コマンドプロンプトから各種ツールをメニュー形式で実行します。

新しいツールを追加する場合:
  1. ハンドラ関数を定義する（例: def run_new_tool(): ...）
  2. ファイル末尾の COMMANDS リストにエントリを追加する
"""

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# ================================================================
# パス設定
# ================================================================
MENU_DIR   = Path(__file__).parent.resolve()   # ws/tool_launcher/
TOOLS_ROOT = MENU_DIR.parent                   # ws/

# ================================================================
# UI ユーティリティ
# ================================================================

WIDTH = 62


def hr(char="="):
    print(char * WIDTH)


def print_menu(title, items, back_label="戻る"):
    """メニューを表示して選択番号を返す。0 = 戻る / 終了"""
    while True:
        print()
        hr()
        print(f"  {title}")
        hr()
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item}")
        hr("-")
        print(f"  0. {back_label}")
        hr()
        choice = input("番号を入力してください: ").strip()
        if choice == "0":
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return int(choice)
        print("  ※ 無効な入力です。もう一度入力してください。")


def wait_enter():
    input("\n  Enter キーでメニューに戻ります...")


# ================================================================
# スクリプト実行
# ================================================================

def python_for(tool_dir: Path) -> str:
    """
    ツールを実行する Python インタプリタを決める。
    ツール専用の .venv があればそれを使い、無ければランチャーと同じ Python を使う。
    ツール名で分岐せず .venv の有無だけで判断するので、全ツールに同じ規則が適用される。
    """
    if sys.platform == "win32":
        venv_python = tool_dir / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = tool_dir / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.is_file() else sys.executable


def run_script(tool_dir_name: str, script_name: str, args: list = None, wait: bool = True):
    """
    TOOLS_ROOT / tool_dir_name にある script_name を実行する。
    wait=False の場合、終了後に Enter 待ちをスキップする（連続実行用）。
    戻り値: 終了コード（int）
    """
    cwd = TOOLS_ROOT / tool_dir_name
    script = cwd / script_name
    args = args or []

    # ツール本体が無い場合、subprocess が FileNotFoundError で落ちて
    # ランチャーごと終了してしまうため、事前に確認してメニューに戻す。
    if not cwd.is_dir():
        print(f"\n  ※ ツールが見つかりません: {cwd}")
        print(f"     {TOOLS_ROOT} 配下に {tool_dir_name} を配置してください。")
        if wait:
            wait_enter()
        return 127
    if not script.is_file():
        print(f"\n  ※ スクリプトが見つかりません: {script}")
        if wait:
            wait_enter()
        return 127

    python = python_for(cwd)
    cmd = [python, script_name] + args

    print()
    cmd_str = " ".join(["python", script_name] + args)
    if python != sys.executable:
        cmd_str += "   （ツール専用の .venv を使用）"
    print(f"  実行: {cmd_str}")
    hr("-")

    result = subprocess.run(cmd, cwd=cwd)

    hr("-")
    if result.returncode == 0:
        print("  完了しました。")
    else:
        print(f"  エラーが発生しました（終了コード: {result.returncode}）")
        # 依存ライブラリ不足（ModuleNotFoundError）は分かりにくいので誘導する
        req = cwd / "requirements.txt"
        if python == sys.executable and req.is_file():
            print("  ※ 「No module named ...」と表示された場合は依存不足です:")
            print(f"     python -m pip install -r {req}")

    if wait:
        wait_enter()
    return result.returncode


# ================================================================
# 土〜金の週プリセット
# ================================================================

def get_sat_to_fri(weeks_ago: int = 0):
    """
    現在日付を基準に、土〜金の週範囲を (start, end) で返す。
      weeks_ago=0 → 今週（直近の土曜〜翌金曜）
      weeks_ago=1 → 先週
    """
    today = date.today()
    # weekday(): 月=0 … 土=5 日=6
    days_since_saturday = (today.weekday() - 5) % 7
    saturday = today - timedelta(days=days_since_saturday)
    start = saturday - timedelta(weeks=weeks_ago)
    end   = start + timedelta(days=6)   # 金曜
    return start, end


def week_label(weeks_ago: int) -> str:
    """メニュー表示用のラベルを生成する"""
    start, end = get_sat_to_fri(weeks_ago)
    prefix = {0: "今週    ", 1: "先週    ", 2: "2週間前 ", 3: "3週間前 "}.get(
        weeks_ago, f"{weeks_ago}週間前"
    )
    return f"{prefix}  土 {start}  〜  金 {end}"


# ================================================================
# 月〜金の週プリセット
# ================================================================

def get_mon_to_fri(weeks_offset: int = 0):
    """
    現在日付を基準に、月〜金の週範囲を (start, end) で返す。
      weeks_offset=0 → 今週  weeks_offset=1 → 来週  weeks_offset=2 → 再来週
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())   # weekday() 月=0
    start  = monday + timedelta(weeks=weeks_offset)
    end    = start  + timedelta(days=4)                # 金曜
    return start, end


def week_label_mon_fri(weeks_offset: int) -> str:
    """メニュー表示用のラベルを生成する（月〜金）"""
    start, end = get_mon_to_fri(weeks_offset)
    # 全角スペースで幅を揃える（「今週」「来週」は2文字、「再来週」は3文字）
    prefix = {0: "今週　", 1: "来週　", 2: "再来週"}.get(weeks_offset, f"{weeks_offset}週後")
    return f"{prefix}  月 {start}  〜  金 {end}"


# ================================================================
# ── ハンドラ: Backlog 週次レポート ──────────────────────────────
# ================================================================

WEEK_PRESET_COUNT = 4   # プリセットとして表示する週数


def run_backlog_report():
    """Backlog 週次レポート生成（--from / --to を選択して実行）"""
    preset_items = [week_label(i) for i in range(WEEK_PRESET_COUNT)]
    preset_items.append("日付を手動入力（YYYY-MM-DD）")

    choice = print_menu("Backlog 週次レポート - 期間選択", preset_items)
    if choice == 0:
        return

    if 1 <= choice <= WEEK_PRESET_COUNT:
        start, end = get_sat_to_fri(choice - 1)
        run_script("backlog_report", "backlog_weekly_report.py",
                   ["--from", str(start), "--to", str(end)])

    elif choice == WEEK_PRESET_COUNT + 1:
        # 手動入力
        print()
        from_str = _input_date("  FROM 日付 (YYYY-MM-DD): ")
        to_str   = _input_date("  TO   日付 (YYYY-MM-DD): ")
        run_script("backlog_report", "backlog_weekly_report.py",
                   ["--from", from_str, "--to", to_str])


def _input_date(prompt: str) -> str:
    """YYYY-MM-DD 形式の日付を入力させる"""
    while True:
        value = input(prompt).strip()
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            print("  ※ YYYY-MM-DD 形式で入力してください。")


# ================================================================
# ── ハンドラ: Excel → Backlog ───────────────────────────────────
# ================================================================

def run_excel_to_backlog():
    """Excel → Backlog 課題登録"""
    options = [
        "ドライラン（変換結果確認のみ・デフォルト）",
        "プレビュー（Markdown ファイルに出力）",
        "実行（Backlog に実際に登録・更新）",
    ]
    choice = print_menu("Excel → Backlog 課題登録", options)
    if choice == 0:
        return

    if choice == 1:
        run_script("excel_to_backlog", "excel_to_backlog.py")
    elif choice == 2:
        run_script("excel_to_backlog", "excel_to_backlog.py", ["--preview"])
    elif choice == 3:
        print()
        confirm = input(
            "  Backlog に実際に登録・更新します。よろしいですか？ [y/N]: "
        ).strip().lower()
        if confirm == "y":
            run_script("excel_to_backlog", "excel_to_backlog.py", ["--execute"])
        else:
            print("  キャンセルしました。")
            wait_enter()


# ================================================================
# ── ハンドラ: Backlog 課題クローン（週次登録） ──────────────────
# ================================================================

def run_backlog_issue_cloner():
    """Backlog 課題クローン（週次登録）- 月〜金の5日分を順次実行"""
    week_items = [week_label_mon_fri(i) for i in range(3)]
    week_choice = print_menu("Backlog 課題クローン - 週を選択", week_items)
    if week_choice == 0:
        return

    weeks_offset = week_choice - 1
    start, _ = get_mon_to_fri(weeks_offset)

    mode_items = [
        "ドライラン（確認のみ・デフォルト）",
        "実行（Backlog に実際に登録・更新）",
    ]
    mode_choice = print_menu("Backlog 課題クローン - 実行モード", mode_items)
    if mode_choice == 0:
        return

    execute = (mode_choice == 2)

    dates = [start + timedelta(days=i) for i in range(5)]
    weekday_names = ["月", "火", "水", "木", "金"]

    today = date.today()
    # 今週かつ当日以前はスキップ対象
    targets = [d for d in dates if not (weeks_offset == 0 and d <= today)]

    # 金・土・日に「今週」を選ぶと対象が 0 件になる。
    # そのまま進むと 1 件も登録していないのに「完了しました」と出てしまうため、
    # ここで明示的に知らせて中断する。
    if not targets:
        print()
        print("  ※ 登録対象の日付がありません。")
        print(f"     今週（月 {dates[0]} 〜 金 {dates[-1]}）は当日以前のみのため、")
        print("     すべてスキップされます。翌週分を登録する場合は「来週」を選択してください。")
        wait_enter()
        return

    print()
    for d in dates:
        date_str = d.strftime("%Y%m%d")

        print()
        hr("-")
        print(f"  [{weekday_names[d.weekday()]}] {d}  ({date_str})")
        hr("-")

        if d not in targets:
            print("  スキップ（当日以前）")
            continue

        args = ["--date", date_str]
        if execute:
            args.append("--execute")

        rc = run_script("backlog_issue_cloner", "backlog_issue_cloner.py",
                        args, wait=False)

        if rc != 0:
            cont = input("  続行しますか？ [y/N]: ").strip().lower()
            if cont != "y":
                print("  中断しました。")
                wait_enter()
                return

    print()
    hr()
    print("  全日程の処理が完了しました。")
    wait_enter()


# ================================================================
# ── ハンドラ: ファイル同期チェック ─────────────────────────────
# ================================================================

def run_file_sync_checker():
    """ファイル同期チェック - 拠点間のファイル差分を検出してレポート生成"""
    options = [
        "通常実行",
        "詳細ログ付き実行（--verbose）",
    ]
    choice = print_menu("ファイル同期チェック", options)
    if choice == 0:
        return

    args = []
    if choice == 2:
        args.append("--verbose")

    run_script("file_sync_checker", "main.py", args)


# ================================================================
# ── ハンドラ: ファイルリスト生成 ────────────────────────────────
# ================================================================

def run_filelist():
    """ファイルリスト生成 - 指定パス配下を走査して自己完結 HTML を生成"""
    options = [
        "通常実行",
        "ドライラン（設定検証のみ）",
        "詳細ログ付き実行（--verbose）",
    ]
    choice = print_menu("ファイルリスト生成", options)
    if choice == 0:
        return

    if choice == 1:
        run_script("filelist", "filelist.py")
    elif choice == 2:
        run_script("filelist", "filelist.py", ["--dry-run"])
    elif choice == 3:
        run_script("filelist", "filelist.py", ["-v"])


# ================================================================
# ── ハンドラ: docgrep（ファイル全文検索）─────────────────────────
# ================================================================

def run_docgrep():
    """docgrep - 対話メニューを起動（docgrep/menu.py に委譲）"""
    run_script("docgrep", "menu.py")


# ================================================================
# コマンド定義
# ================================================================
# 新しいツールを追加するときは、ここにエントリを追加するだけです。
#
# 書き方:
#   {
#       "label":    "メニューに表示する名前",
#       "handler":  run_your_tool,   # 上で定義したハンドラ関数
#       "tool_dir": "ツールのディレクトリ名",  # TOOLS_ROOT からの相対
#   },
# ================================================================

COMMANDS = [
    {
        "label":    "Backlog 週次レポート生成",
        "handler":  run_backlog_report,
        "tool_dir": "backlog_report",
    },
    {
        "label":    "Excel → Backlog 課題登録",
        "handler":  run_excel_to_backlog,
        "tool_dir": "excel_to_backlog",
    },
    {
        "label":    "Backlog 課題クローン（週次登録）",
        "handler":  run_backlog_issue_cloner,
        "tool_dir": "backlog_issue_cloner",
    },
    {
        "label":    "ファイル同期チェック",
        "handler":  run_file_sync_checker,
        "tool_dir": "file_sync_checker",
    },
    {
        "label":    "ファイルリスト生成",
        "handler":  run_filelist,
        "tool_dir": "filelist",
    },
    {
        "label":    "docgrep（ファイル全文検索）",
        "handler":  run_docgrep,
        "tool_dir": "docgrep",
    },
    # ── 新しいコマンドをここに追加 ──────────────────────────────────
    # {
    #     "label":    "新しいツール名",
    #     "handler":  run_new_tool,
    #     "tool_dir": "new_tool",
    # },
]


def menu_labels() -> list:
    """メニュー表示用ラベル。未配置のツールには印を付ける。"""
    labels = []
    for cmd in COMMANDS:
        tool_dir = cmd.get("tool_dir")
        if tool_dir and not (TOOLS_ROOT / tool_dir).is_dir():
            labels.append(f"{cmd['label']}  ※未配置")
        else:
            labels.append(cmd["label"])
    return labels


# ================================================================
# メインループ
# ================================================================

def run_directly(arg: str) -> int:
    """コマンドライン引数で指定された番号のツールを直接実行する。"""
    if not arg.isdigit() or not (1 <= int(arg) <= len(COMMANDS)):
        print(f"  ※ 不正な番号です: {arg}")
        print(f"     1〜{len(COMMANDS)} の番号を指定してください:")
        for i, label in enumerate(menu_labels(), 1):
            print(f"       {i}. {label}")
        return 2

    cmd = COMMANDS[int(arg) - 1]
    print(f"\n  直接実行: {cmd['label']}")
    try:
        cmd["handler"]()
    except KeyboardInterrupt:
        print("\n\n  中断しました。")
        return 130
    except EOFError:
        print("\n\n  入力が終了しました。")
        return 1
    return 0


def main():
    # `python menu.py 6` のように番号を渡すと、そのツールを直接起動する
    if len(sys.argv) > 1:
        return run_directly(sys.argv[1])

    while True:
        try:
            choice = print_menu("ツールメニュー", menu_labels(), back_label="終了")
            if choice == 0:
                print("\n  終了します。\n")
                break
            COMMANDS[choice - 1]["handler"]()
        except KeyboardInterrupt:
            # 長時間実行のツールを Ctrl+C で止めてもメニューには戻れるようにする
            print("\n\n  中断しました。メニューに戻ります。")
        except EOFError:
            # Ctrl+D / Ctrl+Z で標準入力が閉じられた場合
            print("\n\n  入力が終了しました。終了します。\n")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
