"""tool_launcher の日付ロジックと実行ガードのテスト。

  pytest
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import menu  # noqa: E402


# 2026-08-24 は月曜。曜日をずらして検証するときの基準にする。
MONDAY = date(2026, 8, 24)
FRIDAY = date(2026, 8, 28)
SATURDAY = date(2026, 8, 29)
SUNDAY = date(2026, 8, 30)


@pytest.fixture
def freeze_today(monkeypatch):
    """menu.date.today() を固定する。"""
    def _freeze(fixed: date):
        class _FixedDate(date):
            @classmethod
            def today(cls):
                return fixed
        monkeypatch.setattr(menu, "date", _FixedDate)
        return fixed
    return _freeze


# ================================================================
# 土〜金の週（Backlog 週次レポート）
# ================================================================

@pytest.mark.parametrize("today, expected_start", [
    (date(2026, 8, 29), date(2026, 8, 29)),   # 土曜 → 当日が起点
    (date(2026, 8, 30), date(2026, 8, 29)),   # 日曜
    (MONDAY,            date(2026, 8, 22)),   # 月曜 → 直前の土曜
    (FRIDAY,            date(2026, 8, 22)),   # 金曜
])
def test_get_sat_to_fri_start(freeze_today, today, expected_start):
    freeze_today(today)
    start, end = menu.get_sat_to_fri(0)
    assert start == expected_start
    assert start.weekday() == 5          # 土曜
    assert end.weekday() == 4            # 金曜
    assert (end - start).days == 6


def test_get_sat_to_fri_weeks_ago(freeze_today):
    freeze_today(MONDAY)
    this_start, _ = menu.get_sat_to_fri(0)
    prev_start, _ = menu.get_sat_to_fri(1)
    assert (this_start - prev_start).days == 7


# ================================================================
# 月〜金の週（Backlog 課題クローン）
# ================================================================

@pytest.mark.parametrize("offset", [0, 1, 2])
def test_get_mon_to_fri_is_monday_to_friday(freeze_today, offset):
    freeze_today(SATURDAY)
    start, end = menu.get_mon_to_fri(offset)
    assert start.weekday() == 0          # 月曜
    assert end.weekday() == 4            # 金曜
    assert (end - start).days == 4


def test_get_mon_to_fri_offsets_are_one_week_apart(freeze_today):
    freeze_today(MONDAY)
    starts = [menu.get_mon_to_fri(i)[0] for i in range(3)]
    assert (starts[1] - starts[0]).days == 7
    assert (starts[2] - starts[1]).days == 7


# ================================================================
# 「今週」の当日以前スキップ
# ================================================================

def _remaining_targets(today: date) -> list:
    """run_backlog_issue_cloner と同じ条件で対象日を求める。"""
    monday = today - __import__("datetime").timedelta(days=today.weekday())
    dates = [monday + __import__("datetime").timedelta(days=i) for i in range(5)]
    return [d for d in dates if d > today]


@pytest.mark.parametrize("today, expected_count", [
    (MONDAY,            4),
    (date(2026, 8, 25), 3),   # 火
    (date(2026, 8, 26), 2),   # 水
    (date(2026, 8, 27), 1),   # 木
    (FRIDAY,            0),   # 金 → 全スキップ
    (SATURDAY,          0),   # 土 → 全スキップ
    (SUNDAY,            0),   # 日 → 全スキップ
])
def test_this_week_skips_past_dates(today, expected_count):
    assert len(_remaining_targets(today)) == expected_count


# ================================================================
# 週ラベル
# ================================================================

def test_week_label_mon_fri_prefixes_have_equal_width(freeze_today):
    freeze_today(MONDAY)
    prefixes = [menu.week_label_mon_fri(i).split("  ")[0] for i in range(3)]
    assert prefixes == ["今週　", "来週　", "再来週"]
    assert len({len(p) for p in prefixes}) == 1


# ================================================================
# y/N 確認
# ================================================================

@pytest.mark.parametrize("typed, expected", [
    ("y", True), ("Y", True), ("yes", True),
    ("n", False), ("N", False), ("no", False),
])
def test_ask_yes_no_accepts_variants(monkeypatch, typed, expected):
    monkeypatch.setattr("builtins.input", lambda _: typed)
    assert menu.ask_yes_no("実行しますか？") is expected


@pytest.mark.parametrize("default", [True, False])
def test_ask_yes_no_empty_input_uses_default(monkeypatch, default):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert menu.ask_yes_no("実行しますか？", default=default) is default


def test_ask_yes_no_reprompts_on_invalid(monkeypatch, capsys):
    answers = iter(["x", "maybe", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert menu.ask_yes_no("実行しますか？") is True
    assert "y か n を入力してください" in capsys.readouterr().out


# ================================================================
# run_script のガード
# ================================================================

def test_run_script_returns_127_for_missing_tool_dir(capsys):
    rc = menu.run_script("no_such_tool_dir", "main.py", wait=False)
    assert rc == 127
    assert "ツールが見つかりません" in capsys.readouterr().out


def test_run_script_returns_127_for_missing_script(capsys):
    rc = menu.run_script("docgrep", "no_such_script.py", wait=False)
    assert rc == 127
    assert "スクリプトが見つかりません" in capsys.readouterr().out


def test_run_script_does_not_raise_on_missing_tool():
    """ランチャーごと落ちないこと（FileNotFoundError を投げない）。"""
    menu.run_script("definitely_missing", "x.py", wait=False)


# ================================================================
# インタプリタ選択
# ================================================================

def test_python_for_uses_venv_when_present(tmp_path):
    tool = tmp_path / "tool_with_venv"
    if sys.platform == "win32":
        venv = tool / ".venv" / "Scripts" / "python.exe"
    else:
        venv = tool / ".venv" / "bin" / "python"
    venv.parent.mkdir(parents=True)
    venv.touch()
    assert menu.python_for(tool) == str(venv)


def test_python_for_falls_back_to_sys_executable(tmp_path):
    tool = tmp_path / "tool_without_venv"
    tool.mkdir()
    assert menu.python_for(tool) == sys.executable


# ================================================================
# コマンド定義とCLI
# ================================================================

def test_every_command_has_required_keys():
    for cmd in menu.COMMANDS:
        assert cmd["label"]
        assert callable(cmd["handler"])
        assert cmd["tool_dir"]


def test_menu_labels_marks_missing_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(menu, "TOOLS_ROOT", tmp_path)
    assert all("※未配置" in label for label in menu.menu_labels())


def test_menu_labels_are_clean_when_tools_exist():
    labels = menu.menu_labels()
    assert len(labels) == len(menu.COMMANDS)


# ================================================================
# 実行履歴
# ================================================================

@pytest.fixture
def history_file(monkeypatch, tmp_path):
    path = tmp_path / "history.json"
    monkeypatch.setattr(menu, "HISTORY_PATH", path)
    return path


def test_last_label_round_trip(history_file):
    menu.save_last_label("ファイルリスト生成")
    assert menu.load_last_label() == "ファイルリスト生成"


def test_load_last_label_without_history(history_file):
    assert menu.load_last_label() == ""


def test_broken_history_is_ignored(history_file):
    history_file.write_text("{ broken", encoding="utf-8")
    assert menu.load_last_label() == ""


def test_save_last_label_survives_unwritable_path(monkeypatch, tmp_path):
    monkeypatch.setattr(menu, "HISTORY_PATH", tmp_path / "no" / "such" / "h.json")
    menu.save_last_label("何か")          # 例外を投げないこと


def test_default_choice_matches_by_label(history_file):
    commands = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
    menu.save_last_label("B")
    assert menu.default_choice(commands) == 2
    # ツールが増えて位置がずれても、ラベルで追従する
    assert menu.default_choice([{"label": "X"}] + commands) == 3


def test_default_choice_is_none_for_unknown_label(history_file):
    menu.save_last_label("もう存在しないツール")
    assert menu.default_choice([{"label": "A"}]) is None


def test_print_menu_empty_input_uses_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert menu.print_menu("t", ["A", "B"], default=2) == 2


def test_print_menu_empty_input_without_default_reprompts(monkeypatch, capsys):
    answers = iter(["", "1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert menu.print_menu("t", ["A", "B"]) == 1
    assert "無効な入力です" in capsys.readouterr().out


def test_print_menu_explicit_zero_beats_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "0")
    assert menu.print_menu("t", ["A", "B"], default=1) == 0


# ================================================================
# tools.yaml
# ================================================================

def _write_tools_yaml(monkeypatch, tmp_path, text: str):
    path = tmp_path / "tools.yaml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(menu, "TOOLS_YAML", path)
    return path


def test_no_tools_yaml_means_builtin_commands_only(monkeypatch, tmp_path):
    monkeypatch.setattr(menu, "TOOLS_YAML", tmp_path / "absent.yaml")
    assert menu.load_yaml_commands() == []
    assert len(menu.all_commands()) == len(menu.COMMANDS)


def test_tools_yaml_entries_are_appended(monkeypatch, tmp_path):
    _write_tools_yaml(monkeypatch, tmp_path, """
tools:
  - label: "追加ツール"
    tool_dir: "extra_tool"
    script: "run.py"
    options:
      - {label: "通常実行", args: []}
      - {label: "詳細", args: ["-v"]}
""")
    extra = menu.load_yaml_commands()
    assert len(extra) == 1
    assert extra[0]["label"] == "追加ツール"
    assert extra[0]["tool_dir"] == "extra_tool"
    assert callable(extra[0]["handler"])
    assert menu.all_commands()[-1]["label"] == "追加ツール"


def test_tools_yaml_handler_passes_selected_args(monkeypatch, tmp_path):
    _write_tools_yaml(monkeypatch, tmp_path, """
tools:
  - label: "追加ツール"
    tool_dir: "extra_tool"
    script: "run.py"
    options:
      - {label: "通常実行", args: []}
      - {label: "詳細", args: ["-v"]}
""")
    calls = []
    monkeypatch.setattr(menu, "run_script",
                        lambda *a, **kw: calls.append((a, kw)) or 0)
    monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 2)   # 2番目を選択

    menu.load_yaml_commands()[0]["handler"]()
    assert calls == [(("extra_tool", "run.py", ["-v"]), {})]


def test_tools_yaml_without_options_runs_immediately(monkeypatch, tmp_path):
    _write_tools_yaml(monkeypatch, tmp_path, """
tools:
  - label: "引数なしツール"
    tool_dir: "plain_tool"
""")
    calls = []
    monkeypatch.setattr(menu, "run_script",
                        lambda *a, **kw: calls.append(a) or 0)
    menu.load_yaml_commands()[0]["handler"]()
    assert calls == [("plain_tool", "main.py")]      # script は既定の main.py


def test_tools_yaml_skips_invalid_entries(monkeypatch, tmp_path, capsys):
    _write_tools_yaml(monkeypatch, tmp_path, """
tools:
  - label: "tool_dir がない"
  - tool_dir: "label がない"
  - label: "正しいツール"
    tool_dir: "ok_tool"
""")
    extra = menu.load_yaml_commands()
    assert [c["label"] for c in extra] == ["正しいツール"]
    assert "label と tool_dir が必要です" in capsys.readouterr().out


def test_broken_tools_yaml_does_not_raise(monkeypatch, tmp_path, capsys):
    _write_tools_yaml(monkeypatch, tmp_path, "tools: [unclosed\n")
    assert menu.load_yaml_commands() == []
    assert "読み込みに失敗" in capsys.readouterr().out


# ================================================================
# 実行ログ
# ================================================================

def test_run_log_records_command_and_exit_code(history_file):
    menu.append_run_log("excel_to_backlog", "excel_to_backlog.py", ["--execute"], 0)
    runs = menu._load_history()["runs"]
    assert len(runs) == 1
    assert runs[0]["tool"] == "excel_to_backlog"
    assert runs[0]["args"] == ["--execute"]
    assert runs[0]["rc"] == 0
    assert runs[0]["at"]


def test_run_log_keeps_last_label(history_file):
    menu.save_last_label("ファイルリスト生成")
    menu.append_run_log("filelist", "filelist.py", [], 0)
    data = menu._load_history()
    assert data["last_label"] == "ファイルリスト生成"
    assert len(data["runs"]) == 1


def test_run_log_is_capped(history_file, monkeypatch):
    monkeypatch.setattr(menu, "RUN_LOG_LIMIT", 5)
    for i in range(12):
        menu.append_run_log("t", "s.py", [str(i)], 0)
    runs = menu._load_history()["runs"]
    assert len(runs) == 5
    assert [r["args"][0] for r in runs] == ["7", "8", "9", "10", "11"]


def test_run_log_survives_broken_history(history_file):
    history_file.write_text("{ broken", encoding="utf-8")
    menu.append_run_log("t", "s.py", [], 1)
    assert len(menu._load_history()["runs"]) == 1


def test_print_run_log_without_entries(history_file, capsys):
    menu.print_run_log()
    assert "まだありません" in capsys.readouterr().out


def test_print_run_log_marks_failures(history_file, capsys):
    menu.append_run_log("t", "ok.py", [], 0)
    menu.append_run_log("t", "ng.py", ["--execute"], 3)
    out = capsys.readouterr()          # 破棄
    menu.print_run_log()
    out = capsys.readouterr().out
    assert "ng.py --execute" in out
    assert "→ 3" in out
    # 新しい順に並ぶ
    assert out.index("ng.py") < out.index("ok.py")


def test_log_option_exits_zero(history_file):
    assert menu.run_directly("--log") == 0


# ================================================================
# 終了コードの伝播と履歴の記録タイミング
# ================================================================

def _one_command(monkeypatch, rc):
    """ハンドラが rc を返すだけのツールを 1 件だけ登録する。"""
    monkeypatch.setattr(menu, "COMMANDS",
                        [{"label": "テストツール",
                          "handler": lambda: rc,
                          "tool_dir": "test_tool"}])
    monkeypatch.setattr(menu, "load_yaml_commands", lambda: [])


@pytest.mark.parametrize("rc", [0, 1, 3, 130])
def test_direct_launch_propagates_exit_code(monkeypatch, history_file, rc):
    _one_command(monkeypatch, rc)
    assert menu.run_directly("1") == rc


def test_direct_launch_returns_zero_when_cancelled(monkeypatch, history_file):
    _one_command(monkeypatch, None)
    assert menu.run_directly("1") == 0


def test_history_records_executed_tool(monkeypatch, history_file):
    _one_command(monkeypatch, 0)
    menu.run_directly("1")
    assert menu.load_last_label() == "テストツール"


def test_history_skips_cancelled_tool(monkeypatch, history_file):
    _one_command(monkeypatch, None)
    menu.run_directly("1")
    assert menu.load_last_label() == ""


def test_history_keeps_previous_entry_on_cancel(monkeypatch, history_file):
    menu.save_last_label("前に実行したツール")
    _one_command(monkeypatch, None)
    menu.run_directly("1")
    assert menu.load_last_label() == "前に実行したツール"


def test_every_builtin_handler_returns_none_when_cancelled(monkeypatch):
    """0（戻る）を選んだときは全ハンドラが None を返すこと。"""
    monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 0)
    monkeypatch.setattr(menu, "run_script",
                        lambda *a, **kw: pytest.fail("キャンセル時に実行された"))
    for cmd in menu.COMMANDS:
        if cmd["label"].startswith("docgrep"):
            continue          # サブメニューを持たず即実行するため対象外
        assert cmd["handler"]() is None, cmd["label"]


@pytest.mark.parametrize("arg", ["-h", "--help", "-l", "--list"])
def test_help_and_list_exit_zero(arg, capsys):
    assert menu.run_directly(arg) == 0
    assert capsys.readouterr().out.strip()


@pytest.mark.parametrize("arg", ["0", "99", "abc", "--nope", ""])
def test_invalid_argument_exits_two(arg, capsys):
    assert menu.run_directly(arg) == 2
    assert "不正な番号です" in capsys.readouterr().out
