#!/usr/bin/env python3
"""
Tool Launcher - メニュー形式のツール起動スクリプト
================================================
Windows コマンドプロンプトから各種ツールをメニュー形式で実行します。

新しいツールを追加する場合:
  1. ハンドラ関数を定義する（例: def run_new_tool(): ...）
  2. ファイル末尾の COMMANDS リストにエントリを追加する
"""

import os
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

def run_script(tool_dir_name: str, script_name: str, args: list = None):
    """
    TOOLS_ROOT / tool_dir_name にある script_name を実行する。
    """
    cwd = TOOLS_ROOT / tool_dir_name
    args = args or []
    cmd = [sys.executable, script_name] + args

    print()
    cmd_str = " ".join(["python", script_name] + args)
    print(f"  実行: {cmd_str}")
    hr("-")

    result = subprocess.run(cmd, cwd=cwd)

    hr("-")
    if result.returncode == 0:
        print("  完了しました。")
    else:
        print(f"  エラーが発生しました（終了コード: {result.returncode}）")

    wait_enter()


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
# コマンド定義
# ================================================================
# 新しいツールを追加するときは、ここにエントリを追加するだけです。
#
# 書き方:
#   {
#       "label":   "メニューに表示する名前",
#       "handler": run_your_tool,   # 上で定義したハンドラ関数
#   },
# ================================================================

COMMANDS = [
    {
        "label":   "Backlog 週次レポート生成",
        "handler": run_backlog_report,
    },
    {
        "label":   "Excel → Backlog 課題登録",
        "handler": run_excel_to_backlog,
    },
    # ── 新しいコマンドをここに追加 ──────────────────────────────────
    # {
    #     "label":   "新しいツール名",
    #     "handler": run_new_tool,
    # },
]


# ================================================================
# メインループ
# ================================================================

def main():
    labels = [cmd["label"] for cmd in COMMANDS]

    while True:
        choice = print_menu("ツールメニュー", labels, back_label="終了")
        if choice == 0:
            print("\n  終了します。\n")
            break
        COMMANDS[choice - 1]["handler"]()


if __name__ == "__main__":
    main()
