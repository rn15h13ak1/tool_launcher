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


def handler_for(label_part: str):
    """ラベルの一部から COMMANDS のハンドラを取り出す。"""
    for cmd in menu.COMMANDS:
        if label_part in cmd["label"]:
            return cmd["handler"]
    raise AssertionError(f"ツールが見つかりません: {label_part}")


@pytest.fixture(autouse=True)
def reset_batch_mode():
    """テスト間でバッチ実行の状態を持ち越さない。"""
    menu.set_batch_mode()
    yield
    menu.set_batch_mode()


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


def test_declarative_commands_get_a_generated_handler():
    """handler を書いていないエントリにもハンドラが補われること。"""
    declarative = [c for c in menu.COMMANDS if "options" in c or "script" in c]
    assert declarative, "宣言的に定義されたツールが無い"
    assert all(callable(c["handler"]) for c in declarative)


def test_menu_order_is_stable():
    """メニュー番号は運用に影響するため固定する。"""
    assert [c["tool_dir"] for c in menu.COMMANDS] == [
        "backlog_report",
        "excel_to_backlog",
        "backlog_issue_cloner",
        "file_sync_checker",
        "filelist",
        "docgrep",
    ]


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


def test_tools_yaml_option_can_require_confirmation(monkeypatch, tmp_path,
                                                    spy_run_script):
    """組み込みツールと同じ確認プロンプトを tools.yaml でも使えること。"""
    _write_tools_yaml(monkeypatch, tmp_path, """
tools:
  - label: "危険ツール"
    tool_dir: "danger_tool"
    script: "run.py"
    options:
      - {label: "ドライラン", args: ["--dry-run"]}
      - {label: "実行", args: ["--execute"], confirm: "本当に実行しますか？"}
""")
    handler = menu.load_yaml_commands()[0]["handler"]

    menu.set_batch_mode([2])                      # 確認付きの選択肢
    with pytest.raises(menu.BatchInputRequired, match="--yes"):
        handler()
    assert spy_run_script.calls == []

    menu.set_batch_mode([2], assume_yes=True)
    assert handler() == 0
    assert spy_run_script.calls[0]["args"] == ["--execute"]


def test_tools_yaml_option_without_confirm_runs_directly(monkeypatch, tmp_path,
                                                         spy_run_script):
    _write_tools_yaml(monkeypatch, tmp_path, """
tools:
  - label: "普通ツール"
    tool_dir: "plain_tool"
    options:
      - {label: "ドライラン", args: ["--dry-run"]}
""")
    menu.set_batch_mode([1])
    assert menu.load_yaml_commands()[0]["handler"]() == 0
    assert spy_run_script.calls[0]["args"] == ["--dry-run"]


def test_broken_tools_yaml_does_not_raise(monkeypatch, tmp_path, capsys):
    _write_tools_yaml(monkeypatch, tmp_path, "tools: [unclosed\n")
    assert menu.load_yaml_commands() == []
    assert "読み込みに失敗" in capsys.readouterr().out


# ================================================================
# バッチ実行（無人実行）
# ================================================================

def test_parse_args_splits_tool_presets_and_yes():
    assert menu.parse_args(["3", "2", "1"]) == ("3", [2, 1], False)
    assert menu.parse_args(["3", "2", "--yes"]) == ("3", [2], True)
    assert menu.parse_args(["--yes", "5"]) == ("5", [], True)
    assert menu.parse_args(["5"]) == ("5", [], False)


def test_parse_args_rejects_non_numeric_preset():
    first, presets, _ = menu.parse_args(["5", "abc"])
    assert first == "5" and presets is None


def test_batch_mode_consumes_presets_in_order(capsys):
    menu.set_batch_mode([2, 1])
    assert menu.print_menu("週", ["今週", "来週", "再来週"]) == 2
    assert menu.print_menu("モード", ["ドライラン", "実行"]) == 1
    assert "週 → 2. 来週" in capsys.readouterr().out


def test_batch_mode_accepts_zero_as_back():
    menu.set_batch_mode([0])
    assert menu.print_menu("週", ["今週", "来週"]) == 0


def test_batch_mode_errors_when_presets_run_out():
    menu.set_batch_mode([1])
    menu.print_menu("1つ目", ["A", "B"])
    with pytest.raises(menu.BatchInputRequired, match="選択が指定されていません"):
        menu.print_menu("2つ目", ["A", "B"])


def test_batch_mode_errors_on_out_of_range_preset():
    menu.set_batch_mode([9])
    with pytest.raises(menu.BatchInputRequired, match="範囲外"):
        menu.print_menu("週", ["今週", "来週"])


def test_batch_mode_never_calls_input(monkeypatch):
    monkeypatch.setattr("builtins.input",
                        lambda *a: pytest.fail("バッチ実行で入力を求めた"))
    menu.set_batch_mode([1])
    menu.print_menu("週", ["今週"])
    menu.wait_enter()


def test_batch_confirmation_requires_yes_flag():
    menu.set_batch_mode([1])
    with pytest.raises(menu.BatchInputRequired, match="--yes"):
        menu.ask_yes_no("Backlog に登録します。よろしいですか？")


def test_batch_confirmation_passes_with_yes_flag():
    menu.set_batch_mode([1], assume_yes=True)
    assert menu.ask_yes_no("Backlog に登録します。よろしいですか？") is True


def test_batch_default_is_used_for_non_destructive_prompts():
    menu.set_batch_mode([1])
    assert menu.ask_yes_no("続行しますか？", batch_default=False) is False
    assert menu.ask_yes_no("続行しますか？", batch_default=True) is True


def test_yes_flag_overrides_batch_default():
    menu.set_batch_mode([1], assume_yes=True)
    assert menu.ask_yes_no("続行しますか？", batch_default=False) is True


def test_manual_date_entry_is_rejected_in_batch():
    menu.set_batch_mode([1])
    with pytest.raises(menu.BatchInputRequired, match="日付の手動入力"):
        menu._input_date("FROM: ")


@pytest.mark.parametrize("presets", [
    [9],     # 範囲外の選択
    [1],     # 2つ目のサブメニューぶんが足りない
])
def test_run_directly_reports_batch_input_error(monkeypatch, history_file,
                                                capsys, presets):
    def handler():
        menu.print_menu("サブ", ["A", "B"])
        return menu.print_menu("さらにサブ", ["A"])
    monkeypatch.setattr(menu, "COMMANDS",
                        [{"label": "T", "handler": handler, "tool_dir": "t"}])
    monkeypatch.setattr(menu, "load_yaml_commands", lambda: [])
    assert menu.run_directly("1", presets=presets) == 2
    assert "無人実行できません" in capsys.readouterr().out


def test_run_directly_warns_about_unused_answers(monkeypatch, history_file,
                                                 capsys):
    """余った選択は指定ミスの可能性があるので警告する（終了コードは変えない）。"""
    monkeypatch.setattr(menu, "COMMANDS",
                        [{"label": "T", "handler": lambda: 0, "tool_dir": "t"}])
    monkeypatch.setattr(menu, "load_yaml_commands", lambda: [])
    assert menu.run_directly("1", presets=[1, 9]) == 0
    out = capsys.readouterr().out
    assert "使われなかった選択があります: 1 9" in out


def test_run_directly_is_quiet_when_all_answers_used(monkeypatch, history_file,
                                                     capsys):
    def handler():
        return menu.print_menu("サブ", ["A", "B"])
    monkeypatch.setattr(menu, "COMMANDS",
                        [{"label": "T", "handler": handler, "tool_dir": "t"}])
    monkeypatch.setattr(menu, "load_yaml_commands", lambda: [])
    menu.run_directly("1", presets=[2])
    assert "使われなかった選択" not in capsys.readouterr().out


def test_docgrep_entry_has_no_submenu():
    """docgrep はランチャー側にサブメニューを持たない（README の注記と対応）。"""
    entry = next(c for c in menu.COMMANDS if c["tool_dir"] == "docgrep")
    assert not entry.get("options")


def test_run_directly_restores_interactive_mode(monkeypatch, history_file):
    monkeypatch.setattr(menu, "COMMANDS",
                        [{"label": "T", "handler": lambda: 0, "tool_dir": "t"}])
    monkeypatch.setattr(menu, "load_yaml_commands", lambda: [])
    menu.run_directly("1", presets=[1])
    assert menu._BATCH_MODE is False       # 実行後は対話モードに戻る


# ================================================================
# ハンドラ: 課題クローンの週次ループ
# ================================================================

@pytest.fixture
def spy_run_script(monkeypatch):
    """run_script を呼び出し記録に差し替える（既定の戻り値は 0）。"""
    calls = []
    rcs = {"value": 0}

    def fake(tool_dir, script, args=None, wait=True):
        calls.append({"tool": tool_dir, "script": script,
                      "args": list(args or []), "wait": wait})
        rc = rcs["value"]
        return rc(len(calls)) if callable(rc) else rc

    monkeypatch.setattr(menu, "run_script", fake)
    fake.calls = calls
    fake.set_rc = lambda v: rcs.__setitem__("value", v)
    return fake


def _cloner(freeze_today, today, presets, assume_yes=False):
    freeze_today(today)
    menu.set_batch_mode(presets, assume_yes)
    return menu.run_backlog_issue_cloner()


def test_cloner_next_week_dry_run_covers_five_days(freeze_today, spy_run_script):
    rc = _cloner(freeze_today, MONDAY, [2, 1])          # 来週 → ドライラン
    assert rc == 0
    assert len(spy_run_script.calls) == 5
    dates = [c["args"][1] for c in spy_run_script.calls]
    assert dates == ["20260831", "20260901", "20260902", "20260903", "20260904"]
    assert all("--execute" not in c["args"] for c in spy_run_script.calls)
    assert all(c["wait"] is False for c in spy_run_script.calls)


def test_cloner_execute_adds_execute_flag(freeze_today, spy_run_script):
    rc = _cloner(freeze_today, MONDAY, [2, 2], assume_yes=True)
    assert rc == 0
    assert len(spy_run_script.calls) == 5
    assert all("--execute" in c["args"] for c in spy_run_script.calls)


def test_cloner_execute_requires_yes_in_batch(freeze_today, spy_run_script):
    with pytest.raises(menu.BatchInputRequired, match="--yes"):
        _cloner(freeze_today, MONDAY, [2, 2])           # --yes なし
    assert spy_run_script.calls == []                   # 1件も実行しない


def test_cloner_this_week_skips_past_days(freeze_today, spy_run_script):
    rc = _cloner(freeze_today, date(2026, 8, 26), [1, 1])   # 水曜に「今週」
    assert rc == 0
    dates = [c["args"][1] for c in spy_run_script.calls]
    assert dates == ["20260827", "20260828"]            # 木・金のみ


@pytest.mark.parametrize("today", [FRIDAY, SATURDAY, SUNDAY])
def test_cloner_this_week_with_no_targets_runs_nothing(freeze_today,
                                                       spy_run_script,
                                                       capsys, today):
    rc = _cloner(freeze_today, today, [1, 1])
    assert rc is None                                   # キャンセル扱い
    assert spy_run_script.calls == []
    assert "登録対象の日付がありません" in capsys.readouterr().out


def test_cloner_stops_on_error_and_returns_exit_code(freeze_today,
                                                     spy_run_script, capsys):
    spy_run_script.set_rc(lambda n: 3 if n == 2 else 0)  # 2日目で失敗
    rc = _cloner(freeze_today, MONDAY, [2, 1])
    assert rc == 3
    assert len(spy_run_script.calls) == 2               # 3日目以降は実行しない
    assert "中断しました" in capsys.readouterr().out


def test_cloner_continues_past_error_with_yes(freeze_today, spy_run_script):
    spy_run_script.set_rc(lambda n: 3 if n == 2 else 0)
    rc = _cloner(freeze_today, MONDAY, [2, 1], assume_yes=True)
    assert rc == 3                                      # 失敗は結果に残る
    assert len(spy_run_script.calls) == 5               # 最後まで実行する


@pytest.mark.parametrize("presets", [[0], [2, 0]])
def test_cloner_cancel_runs_nothing(freeze_today, spy_run_script, presets):
    assert _cloner(freeze_today, MONDAY, presets) is None
    assert spy_run_script.calls == []


# ================================================================
# ハンドラ: 各ツールに渡す引数
# ================================================================

@pytest.mark.parametrize("choice, expected", [
    (1, ["--from", "2026-08-22", "--to", "2026-08-28"]),   # 今週（土〜金）
    (2, ["--from", "2026-08-15", "--to", "2026-08-21"]),   # 先週
])
def test_backlog_report_passes_week_range(freeze_today, spy_run_script,
                                          choice, expected):
    freeze_today(MONDAY)
    menu.set_batch_mode([choice])
    assert menu.run_backlog_report() == 0
    assert spy_run_script.calls[0]["tool"] == "backlog_report"
    assert spy_run_script.calls[0]["args"] == expected


def test_backlog_report_manual_input_is_blocked_in_batch(freeze_today,
                                                         spy_run_script):
    freeze_today(MONDAY)
    menu.set_batch_mode([5])                    # 5 = 日付を手動入力
    with pytest.raises(menu.BatchInputRequired):
        menu.run_backlog_report()
    assert spy_run_script.calls == []


@pytest.mark.parametrize("choice, expected", [
    (1, []),
    (2, ["--preview"]),
])
def test_excel_to_backlog_passes_mode(spy_run_script, choice, expected):
    menu.set_batch_mode([choice])
    assert handler_for("Excel")() == 0
    assert spy_run_script.calls[0]["args"] == expected


def test_excel_to_backlog_execute_requires_yes(spy_run_script):
    menu.set_batch_mode([3])
    with pytest.raises(menu.BatchInputRequired, match="--yes"):
        handler_for("Excel")()
    assert spy_run_script.calls == []


def test_excel_to_backlog_execute_with_yes(spy_run_script):
    menu.set_batch_mode([3], assume_yes=True)
    assert handler_for("Excel")() == 0
    assert spy_run_script.calls[0]["args"] == ["--execute"]


def test_excel_to_backlog_declined_runs_nothing(monkeypatch, spy_run_script,
                                                capsys):
    monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 3)
    monkeypatch.setattr(menu, "ask_yes_no", lambda *a, **kw: False)
    monkeypatch.setattr(menu, "wait_enter", lambda: None)
    assert handler_for("Excel")() is None
    assert spy_run_script.calls == []
    assert "キャンセルしました" in capsys.readouterr().out


@pytest.mark.parametrize("choice, expected", [
    (1, []),
    (2, ["--dry-run"]),
    (3, ["-v"]),
])
def test_filelist_passes_mode(spy_run_script, choice, expected):
    menu.set_batch_mode([choice])
    assert handler_for("ファイルリスト")() == 0
    assert spy_run_script.calls[0]["tool"] == "filelist"
    assert spy_run_script.calls[0]["args"] == expected


@pytest.mark.parametrize("choice, expected", [
    (1, []),
    (2, ["--verbose"]),
])
def test_file_sync_checker_passes_mode(spy_run_script, choice, expected):
    menu.set_batch_mode([choice])
    assert handler_for("ファイル同期")() == 0
    assert spy_run_script.calls[0]["tool"] == "file_sync_checker"
    assert spy_run_script.calls[0]["args"] == expected


def test_docgrep_delegates_to_its_own_menu(spy_run_script):
    assert handler_for("docgrep")() == 0
    assert spy_run_script.calls == [{"tool": "docgrep", "script": "menu.py",
                                     "args": [], "wait": True}]


@pytest.mark.parametrize("label", [
    "Backlog 週次レポート", "Excel", "ファイル同期", "ファイルリスト",
])
def test_handlers_return_none_and_run_nothing_when_cancelled(spy_run_script,
                                                             label):
    menu.set_batch_mode([0])
    assert handler_for(label)() is None
    assert spy_run_script.calls == []


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


@pytest.mark.parametrize("arg", ["--help", "--list", "7", "abc"])
def test_tools_yaml_is_read_once_per_invocation(monkeypatch, history_file, arg):
    """tools.yaml の読み込みが 1 回で済むこと。"""
    calls = []
    real = menu.load_yaml_commands
    monkeypatch.setattr(menu, "load_yaml_commands",
                        lambda: calls.append(1) or real())
    menu.run_directly(arg)
    assert len(calls) == 1


@pytest.mark.parametrize("arg", ["-h", "--help", "-l", "--list"])
def test_help_and_list_exit_zero(arg, capsys):
    assert menu.run_directly(arg) == 0
    assert capsys.readouterr().out.strip()


@pytest.mark.parametrize("arg", ["0", "99", "abc", "--nope", ""])
def test_invalid_argument_exits_two(arg, capsys):
    assert menu.run_directly(arg) == 2
    assert "不正な番号です" in capsys.readouterr().out
