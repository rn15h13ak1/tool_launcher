@echo off
chcp 65001 > nul
setlocal

rem ================================================================
rem  Tool Launcher - 起動バッチ
rem  どのディレクトリから呼び出しても正しく動作します。
rem ================================================================

rem ── このバッチ自身のディレクトリを基準パスとして取得 ─────────────
rem    %~dp0 は末尾に \ が付くため除去する
set "MENU_DIR=%~dp0"
if "%MENU_DIR:~-1%"=="\" set "MENU_DIR=%MENU_DIR:~0,-1%"

rem ── .env.bat を読み込み（存在する場合のみ） ──────────────────────
rem    個人の環境設定（パスや activate 先）はこのファイルに記述します。
rem    .env.bat は .gitignore により Git 管理対象外です。
if exist "%MENU_DIR%\.env.bat" (
    call "%MENU_DIR%\.env.bat"
)

rem ── プリコマンドを実行（例: 仮想環境の activate） ─────────────────
rem    TOOLS_PRE_COMMAND が設定されている場合のみ実行します。
if defined TOOLS_PRE_COMMAND (
    call "%TOOLS_PRE_COMMAND%"
)

rem ── Python インタプリタの指定 ─────────────────────────────────────
rem    TOOLS_PYTHON が未設定の場合は PATH 上の python を使用します。
if not defined TOOLS_PYTHON set "TOOLS_PYTHON=python"

rem ── メニューを起動 ────────────────────────────────────────────────
"%TOOLS_PYTHON%" "%MENU_DIR%\menu.py"

endlocal
pause
