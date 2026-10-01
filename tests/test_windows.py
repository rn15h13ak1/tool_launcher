"""Windows 環境への対応を守るテスト。

macOS / Linux では気づけない退行を検出する。本ランチャーは Windows の
コマンドプロンプトから使う前提で `menu.bat` を配っているため、Windows で
起動できないと使い物にならない。

作りは ../file_sync_checker/tests/test_windows.py に揃えている
（提案 ../proposals/windows-console-cp932.md）。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import menu  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# コンソールに出力するソース。
# Windows の日本語コンソールは既定で CP932 のため、CP932 に無い文字を print すると
# 文字化けではなく UnicodeEncodeError で落ちる。menu.bat をダブルクリックした場合、
# メニューの最初の画面すら出ない。
CONSOLE_SOURCES = ("menu.py",)

# tools.example.yaml の label は、tools.yaml にコピーするとそのまま画面に出る。
MENU_TEXT_SOURCES = ("tools.example.yaml",)


def _emoji_tools_yaml(tmp_path: Path) -> Path:
    """CP932 に無い文字をラベルに持つ tools.yaml を作る。"""
    path = tmp_path / "tools.yaml"
    path.write_text(
        'tools:\n'
        '  - label: "\U0001F680 デプロイ"\n'
        '    tool_dir: "deploy"\n',
        encoding="utf-8",
    )
    return path


def _unencodable(text: str) -> set:
    bad = set()
    for ch in set(text):
        if ord(ch) < 128:
            continue
        try:
            ch.encode("cp932")
        except UnicodeEncodeError:
            bad.add(ch)
    return bad


class TestCp932Safety:
    """画面に出る文字がすべて CP932 で表現できること。"""

    @pytest.mark.parametrize("name", CONSOLE_SOURCES + MENU_TEXT_SOURCES)
    def test_sources_are_cp932_safe(self, name):
        bad = _unencodable((ROOT / name).read_text(encoding="utf-8"))
        assert bad == set(), (
            f"{name} に CP932 で表現できない文字があります: "
            + ", ".join(f"U+{ord(c):04X} {c!r}" for c in sorted(bad))
            + "。Windows の日本語コンソールで UnicodeEncodeError になります。"
        )

    def test_detects_a_known_bad_character(self):
        """検査自体が機能していることを確かめる (em dash は CP932 に無い)。"""
        assert _unencodable("作成完了 — 件名") == {"—"}

    @pytest.mark.parametrize("ch", "←※〜─→　")
    def test_common_symbols_are_safe(self, ch):
        """実際に使っている記号が CP932 にあること。"""
        assert _unencodable(ch) == set()

    def test_menu_labels_are_cp932_safe(self):
        """組み込みツールのラベルが画面に出せること。"""
        for cmd in menu.COMMANDS:
            assert _unencodable(cmd["label"]) == set(), cmd["label"]

    def test_week_labels_are_cp932_safe(self):
        """週ラベルは全角スペースと波ダッシュを含むため個別に見る。"""
        for i in range(menu.CLONER_WEEK_PRESET_COUNT):
            assert _unencodable(menu.week_label_mon_fri(i)) == set()
        for i in range(menu.WEEK_PRESET_COUNT):
            assert _unencodable(menu.week_label(i)) == set()


class TestConsoleSafety:
    """外から来る文字で落ちないこと。

    ソースの文字は TestCp932Safety で CP932 に収めているが、tools.yaml のラベルは
    利用者が書くため防げない。絵文字を 1 つ書かれるとメニューの一覧表示で落ち、
    何もできずに終わる。
    """

    @staticmethod
    def _cp932_stdout():
        """Windows の日本語コンソールを模した差し替え用のストリーム。"""
        return io.TextIOWrapper(io.BytesIO(), encoding="cp932", errors="strict")

    def test_unencodable_label_crashes_without_the_guard(self, monkeypatch,
                                                         tmp_path):
        """前提: 手当てが無いと落ちる。外したときに何が起きるかを残す。"""
        stream = self._cp932_stdout()
        monkeypatch.setattr(sys, "stdout", stream)
        monkeypatch.setattr(menu, "TOOLS_YAML", _emoji_tools_yaml(tmp_path))
        with pytest.raises(UnicodeEncodeError):
            menu.print_tool_list()

    def test_guard_replaces_unencodable_label(self, monkeypatch, tmp_path):
        """手当てがあると、その文字だけ ? になる。"""
        stream = self._cp932_stdout()
        monkeypatch.setattr(sys, "stdout", stream)
        monkeypatch.setattr(menu, "TOOLS_YAML", _emoji_tools_yaml(tmp_path))

        menu.make_console_safe([stream])
        menu.print_tool_list()          # 落ちないこと

        stream.flush()
        out = stream.buffer.getvalue().decode("cp932")
        assert "? デプロイ" in out

    def test_guard_leaves_utf8_console_alone(self):
        """UTF-8 のコンソール（macOS など）では何もしない。"""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8",
                                  errors="strict")
        menu.make_console_safe([stream])
        assert stream.errors == "strict"

    def test_guard_survives_a_stream_without_reconfigure(self):
        """reconfigure を持たないストリームでも例外にしない。"""
        menu.make_console_safe([io.StringIO()])

    def test_guard_is_called_before_anything_else(self):
        """入口で、ほかの処理より先に呼んでいること。"""
        src = (ROOT / "menu.py").read_text(encoding="utf-8")
        body = src.split("def main():", 1)[1]
        assert "make_console_safe()" in body
        called = body.index("make_console_safe()")
        assert called < body.index("parse_args("), (
            "引数の解析より後に呼んでいます。解析のエラー表示で落ちます。"
        )


class TestMenuBat:
    """menu.bat が cmd.exe で正しく解釈される形であること。"""

    @pytest.fixture
    def raw(self) -> bytes:
        return (ROOT / "menu.bat").read_bytes()

    def test_uses_crlf(self, raw):
        """cmd.exe は LF だけの .bat を誤動作させることがある。"""
        assert b"\r\n" in raw
        assert re.search(rb"[^\r]\n", raw) is None, "LF だけの行があります"

    def test_is_ascii_only(self, raw):
        """コンソールのコードページに依存しないよう ASCII に収める。"""
        raw.decode("ascii")   # 例外が出なければ OK

    def test_calls_menu_py(self, raw):
        assert b"menu.py" in raw

    def test_falls_back_from_py_launcher_to_python(self, raw):
        text = raw.decode("ascii")
        assert "py -3" in text and "python --version" in text

    def test_passes_arguments_through(self, raw):
        """menu.bat 3 2 1 のような無人実行を通すため。"""
        assert "menu.py %*" in raw.decode("ascii")

    def test_pause_is_skipped_when_arguments_are_given(self, raw):
        """無人実行では pause で待ち続けないこと。

        兄弟リポジトリは常に pause するが、本ランチャーはタスクスケジューラから
        引数付きで呼ぶ使い方を案内しているため、そこだけ変えている。
        """
        text = raw.decode("ascii")
        assert 'if "%~1"=="" pause' in text
        assert re.search(r"^\s*pause\s*$", text, re.M) is not None, (
            "エラー時にウィンドウを残す pause が無くなっています"
        )

    def test_returns_exit_code(self, raw):
        """直接起動の成否を呼び出し側で判定できるようにする。"""
        assert "exit /b %RC%" in raw.decode("ascii")

    def test_uses_pushd_for_unc_paths(self, raw):
        """共有ドライブ上の UNC パスから起動しても動くようにする。"""
        text = raw.decode("ascii")
        assert "pushd" in text and "popd" in text

    def test_gitattributes_pins_crlf(self):
        """チェックアウト時に LF へ正規化されないよう固定する。"""
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        assert "*.bat" in attrs and "eol=crlf" in attrs


class TestWindowsInterpreter:
    """Windows でツールの .venv を正しく選ぶこと。"""

    def test_picks_scripts_python_exe_on_windows(self, monkeypatch, tmp_path):
        """macOS で開発していると bin/python 側しか通らないため明示的に見る。"""
        monkeypatch.setattr(menu.sys, "platform", "win32")
        tool = tmp_path / "tool"
        venv = tool / ".venv" / "Scripts" / "python.exe"
        venv.parent.mkdir(parents=True)
        venv.touch()
        assert menu.python_for(tool) == str(venv)

    def test_ignores_posix_venv_on_windows(self, monkeypatch, tmp_path):
        """Windows で bin/python を拾うと起動できない。"""
        monkeypatch.setattr(menu.sys, "platform", "win32")
        tool = tmp_path / "tool"
        posix = tool / ".venv" / "bin" / "python"
        posix.parent.mkdir(parents=True)
        posix.touch()
        assert menu.python_for(tool) == sys.executable
