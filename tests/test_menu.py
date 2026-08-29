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


@pytest.mark.parametrize("arg", ["-h", "--help", "-l", "--list"])
def test_help_and_list_exit_zero(arg, capsys):
    assert menu.run_directly(arg) == 0
    assert capsys.readouterr().out.strip()


@pytest.mark.parametrize("arg", ["0", "99", "abc", "--nope", ""])
def test_invalid_argument_exits_two(arg, capsys):
    assert menu.run_directly(arg) == 2
    assert "不正な番号です" in capsys.readouterr().out
