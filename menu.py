#!/usr/bin/env python3
"""
Tool Launcher - メニュー形式のツール起動スクリプト
================================================
Windows コマンドプロンプトから各種ツールをメニュー形式で実行します。

新しいツールを追加する場合:
  1. ハンドラ関数を定義する（例: def run_new_tool(): ...）
  2. ファイル末尾の COMMANDS リストにエントリを追加する
"""

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
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

# ── バッチ実行（無人実行）用の状態 ──────────────────────────────
# コマンドラインでサブ選択を渡すと、その回答を先読みして使う。
# 入力待ちが発生しないので cron やタスクスケジューラから起動できる。
_PRESET_ANSWERS = []      # 例: python menu.py 3 2 1 → [2, 1]
_BATCH_MODE = False       # サブ選択が与えられたら True
_ASSUME_YES = False       # --yes 指定時のみ True


class BatchInputRequired(Exception):
    """バッチ実行中に、用意されていない入力を求められた。"""


def set_batch_mode(answers: list = None, assume_yes: bool = False) -> None:
    """バッチ実行の状態を設定する（answers が空ならバッチ実行しない）。"""
    global _PRESET_ANSWERS, _BATCH_MODE, _ASSUME_YES
    _PRESET_ANSWERS = list(answers or [])
    _BATCH_MODE = bool(answers)
    _ASSUME_YES = assume_yes


def unused_answers() -> list:
    """使われずに残ったサブ選択を返す（指定ミスの検出用）。"""
    return list(_PRESET_ANSWERS)


def hr(char="="):
    print(char * WIDTH)


def print_menu(title, items, back_label="戻る", default=None):
    """
    メニューを表示して選択番号を返す。0 = 戻る / 終了
    default に番号を渡すと、空 Enter でその番号を選べる。
    バッチ実行中はコマンドラインで指定された回答を順に使う。
    """
    if _BATCH_MODE:
        if not _PRESET_ANSWERS:
            raise BatchInputRequired(
                f"「{title}」の選択が指定されていません "
                f"（1〜{len(items)}、0=戻る）"
            )
        choice = _PRESET_ANSWERS.pop(0)
        if not (0 <= choice <= len(items)):
            raise BatchInputRequired(
                f"「{title}」の選択 {choice} は範囲外です "
                f"（1〜{len(items)}、0=戻る）"
            )
        label = items[choice - 1] if choice else back_label
        print(f"\n  {title} → {choice}. {label}")
        return choice

    while True:
        print()
        hr()
        print(f"  {title}")
        hr()
        for i, item in enumerate(items, 1):
            mark = " ←前回" if default == i else ""
            print(f"  {i}. {item}{mark}")
        hr("-")
        print(f"  0. {back_label}")
        hr()
        prompt = ("番号を入力してください"
                  + (f" [Enter={default}]: " if default else ": "))
        choice = input(prompt).strip()
        if not choice and default:
            return default
        if choice == "0":
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return int(choice)
        print("  ※ 無効な入力です。もう一度入力してください。")


def ask_yes_no(prompt: str, default: bool = False,
               batch_default: bool = None) -> bool:
    """
    y/n の確認を取る。空 Enter は default を採用する。

    バッチ実行中の扱い:
      --yes 指定時          → 常に yes
      batch_default 指定時  → その値（エラー継続の可否など、破壊的でない確認）
      それ以外              → エラー（Backlog への書き込みを黙って通さない）
    """
    if _BATCH_MODE:
        if _ASSUME_YES:
            print(f"  {prompt} → yes（--yes）")
            return True
        if batch_default is not None:
            print(f"  {prompt} → {'yes' if batch_default else 'no'}（無人実行の既定）")
            return batch_default
        raise BatchInputRequired(
            f"確認が必要です: {prompt}  → 実行するには --yes を指定してください"
        )

    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        answer = input(f"  {prompt}{suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  ※ y か n を入力してください。")


def wait_enter():
    # バッチ実行では入力待ちしない（stdin が無い環境で止まらないようにする）
    if _BATCH_MODE:
        return
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
    append_run_log(tool_dir_name, script_name, args, result.returncode)

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
        return None

    if 1 <= choice <= WEEK_PRESET_COUNT:
        start, end = get_sat_to_fri(choice - 1)
        return run_script("backlog_report", "backlog_weekly_report.py",
                          ["--from", str(start), "--to", str(end)])

    # 手動入力
    print()
    from_str = _input_date("  FROM 日付 (YYYY-MM-DD): ")
    to_str   = _input_date("  TO   日付 (YYYY-MM-DD): ")
    return run_script("backlog_report", "backlog_weekly_report.py",
                      ["--from", from_str, "--to", to_str])


def _input_date(prompt: str) -> str:
    """YYYY-MM-DD 形式の日付を入力させる"""
    if _BATCH_MODE:
        raise BatchInputRequired(
            "日付の手動入力はバッチ実行では使えません（週プリセットを選んでください）"
        )
    while True:
        value = input(prompt).strip()
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            print("  ※ YYYY-MM-DD 形式で入力してください。")




# ================================================================
# ── ハンドラ: Backlog 課題クローン（週次登録） ──────────────────
# ================================================================

CLONER_WEEK_PRESET_COUNT = 3   # 今週・来週・再来週


def run_backlog_issue_cloner():
    """Backlog 課題クローン（週次登録）- 月〜金の5日分を順次実行"""
    week_items = [week_label_mon_fri(i) for i in range(CLONER_WEEK_PRESET_COUNT)]
    week_choice = print_menu("Backlog 課題クローン - 週を選択", week_items)
    if week_choice == 0:
        return None

    weeks_offset = week_choice - 1
    start, _ = get_mon_to_fri(weeks_offset)

    mode_items = [
        "ドライラン（確認のみ・デフォルト）",
        "実行（Backlog に実際に登録・更新）",
    ]
    mode_choice = print_menu("Backlog 課題クローン - 実行モード", mode_items)
    if mode_choice == 0:
        return None

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
        return None

    # Backlog を書き換えるのは複数日ぶんなので、対象を提示して一度確認する。
    if execute:
        print()
        print(f"  {len(targets)} 件を Backlog に登録・更新します:")
        for d in targets:
            print(f"    {weekday_names[d.weekday()]} {d}")
        if not ask_yes_no("よろしいですか？"):
            print("  キャンセルしました。")
            wait_enter()
            return None

    print()
    worst_rc = 0
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
            worst_rc = rc
            # 無人実行ではエラーが出たら止める（破壊的操作の確認ではないので
            # --yes は要求せず、既定で「中断」とする）
            if not ask_yes_no("続行しますか？", batch_default=False):
                print("  中断しました。")
                wait_enter()
                return rc

    print()
    hr()
    print("  全日程の処理が完了しました。")
    wait_enter()
    return worst_rc








# ================================================================
# ツール定義からハンドラを作る
# ================================================================

def make_tool_handler(entry: dict):
    """
    ツール定義（label / tool_dir / script / options）からハンドラを作る。
    「選択肢を選んで引数付きで実行するだけ」のツールはこれで賄える。
    組み込みツールと tools.yaml のツールで同じ仕組みを使う。
    """
    label    = entry["label"]
    tool_dir = entry["tool_dir"]
    script   = entry.get("script", "main.py")
    options  = entry.get("options") or []

    def handler():
        # 選択肢が無いツールはそのまま実行する
        if not options:
            return run_script(tool_dir, script)

        choice = print_menu(label, [o["label"] for o in options])
        if choice == 0:
            return None

        option = options[choice - 1]
        confirm = option.get("confirm")
        if confirm:
            print()
            if not ask_yes_no(confirm):
                print("  キャンセルしました。")
                wait_enter()
                return None

        return run_script(tool_dir, script, list(option.get("args") or []))

    handler.__doc__ = label
    return handler


# ================================================================
# コマンド定義
# ================================================================
# 新しいツールを追加するときは、ここにエントリを追加するだけです。
#
# 選択肢を選んで実行するだけのツール:
#   {
#       "label":    "メニューに表示する名前",
#       "tool_dir": "ツールのディレクトリ名",   # TOOLS_ROOT からの相対
#       "script":   "main.py",                 # 省略時 main.py
#       "options": [                           # 省略時は引数なしで即実行
#           {"label": "通常実行", "args": []},
#           {"label": "実行", "args": ["--execute"],
#            "confirm": "本当に実行しますか？"},   # 確認したい選択肢に付ける
#       ],
#   },
#
# 日付選択など独自の操作が要るツール:
#   {
#       "label":    "メニューに表示する名前",
#       "handler":  run_your_tool,             # 自分で書いたハンドラ関数
#       "tool_dir": "ツールのディレクトリ名",
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
        "tool_dir": "excel_to_backlog",
        "script":   "excel_to_backlog.py",
        "options": [
            {"label": "ドライラン（変換結果確認のみ・デフォルト）", "args": []},
            {"label": "プレビュー（Markdown ファイルに出力）", "args": ["--preview"]},
            {"label": "実行（Backlog に実際に登録・更新）", "args": ["--execute"],
             "confirm": "Backlog に実際に登録・更新します。よろしいですか？"},
        ],
    },
    {
        "label":    "Backlog 課題クローン（週次登録）",
        "handler":  run_backlog_issue_cloner,
        "tool_dir": "backlog_issue_cloner",
    },
    {
        "label":    "ファイル同期チェック",
        "tool_dir": "file_sync_checker",
        "script":   "main.py",
        "options": [
            {"label": "通常実行", "args": []},
            {"label": "詳細ログ付き実行（--verbose）", "args": ["--verbose"]},
        ],
    },
    {
        "label":    "ファイルリスト生成",
        "tool_dir": "filelist",
        "script":   "filelist.py",
        "options": [
            {"label": "通常実行", "args": []},
            {"label": "ドライラン（設定検証のみ）", "args": ["--dry-run"]},
            {"label": "詳細ログ付き実行（--verbose）", "args": ["-v"]},
        ],
    },
    {
        "label":    "docgrep（ファイル全文検索）",
        "tool_dir": "docgrep",
        "script":   "menu.py",          # docgrep 側の対話メニューに委譲する
    },
    # ── 新しいコマンドをここに追加 ──────────────────────────────────
]

# 宣言だけのエントリにハンドラを補う
for _entry in COMMANDS:
    _entry.setdefault("handler", make_tool_handler(_entry))


# ================================================================
# tools.yaml による追加ツール（任意）
# ================================================================
# サブメニューが「引数を選ぶだけ」の単純なツールは、menu.py を編集せずに
# tools.yaml で追加できる。ファイルが無ければ何もしない。
#
#   tools:
#     - label: "新しいツール"
#       tool_dir: "new_tool"
#       script: "main.py"
#       options:                        # 省略時は引数なしで即実行
#         - {label: "通常実行", args: []}
#         - {label: "詳細ログ", args: ["-v"]}
#         - {label: "実行", args: ["--execute"],
#            confirm: "本当に実行しますか？"}   # 確認したい選択肢に付ける
#
# 組み込みツールと同じ make_tool_handler を使うので、挙動は完全に同じ。
# ================================================================

TOOLS_YAML = MENU_DIR / "tools.yaml"


def load_yaml_commands() -> list:
    """tools.yaml を読み込んで COMMANDS 形式のリストを返す。"""
    if not TOOLS_YAML.is_file():
        return []
    try:
        import yaml
    except ImportError:
        print(f"  ※ PyYAML が無いため {TOOLS_YAML.name} を読み込めません。")
        return []
    try:
        with TOOLS_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"  ※ {TOOLS_YAML.name} の読み込みに失敗しました: {e}")
        return []

    commands = []
    for entry in data.get("tools") or []:
        if not isinstance(entry, dict) or not entry.get("label") or not entry.get("tool_dir"):
            print(f"  ※ {TOOLS_YAML.name}: label と tool_dir が必要です: {entry!r}")
            continue
        commands.append({
            "label":    entry["label"],
            "handler":  make_tool_handler(entry),
            "tool_dir": entry["tool_dir"],
        })
    return commands


def all_commands() -> list:
    """組み込みのツール + tools.yaml のツール。"""
    return COMMANDS + load_yaml_commands()


def menu_labels(commands: list = None) -> list:
    """メニュー表示用ラベル。未配置のツールには印を付ける。"""
    labels = []
    for cmd in (all_commands() if commands is None else commands):
        tool_dir = cmd.get("tool_dir")
        if tool_dir and not (TOOLS_ROOT / tool_dir).is_dir():
            labels.append(f"{cmd['label']}  ※未配置")
        else:
            labels.append(cmd["label"])
    return labels


# ================================================================
# 実行履歴（前回選んだツールを覚えて既定にする）
# ================================================================

HISTORY_PATH = Path.home() / ".tool_launcher_history.json"
RUN_LOG_LIMIT = 50          # 実行ログとして保持する件数


def load_last_label() -> str:
    """前回実行したツールのラベルを返す。読めなければ空文字。"""
    try:
        with HISTORY_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        label = data.get("last_label", "")
        return label if isinstance(label, str) else ""
    except Exception:
        # 履歴が壊れていてもランチャーの動作は妨げない
        return ""


def _load_history() -> dict:
    """履歴ファイル全体を読む。読めなければ空 dict。"""
    try:
        with HISTORY_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_history(data: dict) -> None:
    """履歴ファイルを書く。失敗しても無視する。"""
    try:
        HISTORY_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def save_last_label(label: str) -> None:
    """実行したツールのラベルを保存する。失敗しても無視する。"""
    data = _load_history()
    data["last_label"] = label
    _write_history(data)


def append_run_log(tool_dir: str, script: str, args: list, rc: int) -> None:
    """
    実行したコマンドと結果を履歴に追記する。
    Backlog を書き換える操作（--execute）が「いつ・何を」実行されたか
    後から追えるようにするのが目的。
    """
    data = _load_history()
    runs = data.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append({
        "at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tool":   tool_dir,
        "script": script,
        "args":   list(args),
        "rc":     rc,
    })
    data["runs"] = runs[-RUN_LOG_LIMIT:]
    _write_history(data)


def print_run_log() -> None:
    """直近の実行ログを表示する。"""
    runs = _load_history().get("runs") or []
    if not runs:
        print("  実行ログはまだありません。")
        return
    print(f"  直近の実行 {len(runs)} 件（新しい順）  {HISTORY_PATH}")
    hr("-")
    for run in reversed(runs):
        args = " ".join(run.get("args") or [])
        mark = "  " if run.get("rc") == 0 else " !"
        print(f" {mark} {run.get('at', '')}  "
              f"{run.get('tool', '')}/{run.get('script', '')} {args}".rstrip()
              + f"   → {run.get('rc')}")


def default_choice(commands: list) -> int:
    """
    前回実行したツールの番号を返す（無ければ None）。
    番号ではなくラベルで覚えるので、tools.yaml の増減で位置がずれても追従する。
    """
    last = load_last_label()
    if not last:
        return None
    for i, cmd in enumerate(commands, 1):
        if cmd["label"] == last:
            return i
    return None


# ================================================================
# メインループ
# ================================================================

def print_tool_list(indent: str = "  ", commands: list = None) -> None:
    """ツール番号とラベルの一覧を表示する。"""
    for i, label in enumerate(menu_labels(commands), 1):
        print(f"{indent}{i}. {label}")


def print_help(commands: list = None) -> None:
    print("Tool Launcher - メニュー形式のツール起動スクリプト")
    print()
    print("使い方:")
    print("  python menu.py                    メニューを表示する")
    print("  python menu.py <番号>             指定した番号のツールを起動する")
    print("  python menu.py <番号> <選択...>   サブメニューの選択も指定して")
    print("                                    無人実行する（入力待ちなし）")
    print("  python menu.py --list             ツール一覧を表示する")
    print("  python menu.py --log              直近の実行ログを表示する")
    print("  python menu.py --help             このヘルプを表示する")
    print()
    print("オプション:")
    print("  --yes    無人実行時に確認プロンプトを自動承認する")
    print("           （指定しないと確認箇所でエラー終了する）")
    print()
    print("例:")
    print("  python menu.py 5 2         ファイルリスト生成をドライランで実行")
    print("  python menu.py 3 2 1       課題クローン: 来週 → ドライラン")
    print("  python menu.py 3 2 2 --yes 課題クローン: 来週 → 実行（確認を承認）")
    print()
    print("ツール一覧:")
    print_tool_list(commands=commands)


def parse_args(argv: list):
    """
    コマンドライン引数を (最初の引数, サブ選択リスト, --yes) に分解する。
    """
    assume_yes = "--yes" in argv
    positional = [a for a in argv if a != "--yes"]
    first = positional[0] if positional else None
    presets = []
    for a in positional[1:]:
        if not a.isdigit():
            return first, None, assume_yes      # None = 不正なサブ選択
        presets.append(int(a))
    return first, presets, assume_yes


def run_directly(arg: str, presets: list = None, assume_yes: bool = False) -> int:
    """コマンドライン引数で指定された番号のツールを直接実行する。"""
    if arg == "--log":
        print_run_log()
        return 0

    # tools.yaml の読み込みは 1 回だけにして、以降は同じリストを使い回す
    commands = all_commands()

    if arg in ("-h", "--help"):
        print_help(commands)
        return 0
    if arg in ("-l", "--list"):
        print_tool_list(commands=commands)
        return 0

    if not arg.isdigit() or not (1 <= int(arg) <= len(commands)):
        print(f"  ※ 不正な番号です: {arg}")
        print(f"     1〜{len(commands)} の番号を指定してください:")
        print_tool_list("       ", commands)
        print("     ヘルプ: python menu.py --help")
        return 2

    cmd = commands[int(arg) - 1]
    set_batch_mode(presets, assume_yes)
    print(f"\n  直接実行: {cmd['label']}")
    try:
        rc = cmd["handler"]()
    except BatchInputRequired as e:
        print(f"\n  ※ 無人実行できません: {e}")
        print("     ヘルプ: python menu.py --help")
        return 2
    except KeyboardInterrupt:
        print("\n\n  中断しました。")
        return 130
    except EOFError:
        print("\n\n  入力が終了しました。")
        return 1
    else:
        # 使われなかった選択が残っていたら指定ミスの可能性がある
        leftover = unused_answers()
        if leftover:
            print(f"\n  ※ 使われなかった選択があります: "
                  f"{' '.join(str(n) for n in leftover)}")
            print("     指定が実際のメニュー構成とずれていないか確認してください。")
    finally:
        set_batch_mode()          # 対話実行に戻す

    # ハンドラは実行したら終了コード、キャンセルなら None を返す
    if rc is None:
        return 0
    save_last_label(cmd["label"])
    return rc


def main():
    # `python menu.py 6` のように番号を渡すと、そのツールを直接起動する。
    # さらにサブ選択を続けると入力待ちなしで無人実行する。
    if len(sys.argv) > 1:
        first, presets, assume_yes = parse_args(sys.argv[1:])
        if presets is None:
            print("  ※ サブメニューの選択は数字で指定してください。")
            print("     例: python menu.py 3 2 1")
            print("     ヘルプ: python menu.py --help")
            return 2
        return run_directly(first, presets, assume_yes)

    while True:
        try:
            # tools.yaml の編集を再起動なしで反映するため、毎回読み直す
            commands = all_commands()
            choice = print_menu("ツールメニュー", menu_labels(commands),
                                back_label="終了",
                                default=default_choice(commands))
            if choice == 0:
                print("\n  終了します。\n")
                break
            selected = commands[choice - 1]
            # 実行した場合のみ「前回」として記録する
            # （サブメニューで戻っただけのツールを既定にしない）
            if selected["handler"]() is not None:
                save_last_label(selected["label"])
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
