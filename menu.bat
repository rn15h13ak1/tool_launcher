@echo off
chcp 65001 > nul
setlocal

rem ================================================================
rem  Tool Launcher
rem  Works from any directory.
rem ================================================================

rem -- Get the directory of this batch file (ws	ool_launcher\) ----
rem    %%~dp0 includes a trailing backslash, so remove it.
set "MENU_DIR=%~dp0"
if "%MENU_DIR:~-1%"=="" set "MENU_DIR=%MENU_DIR:~0,-1%"

rem -- Load .env.bat if it exists ------------------------------------
rem    Copy .env.bat.example to .env.bat and edit for your environment.
rem    .env.bat is excluded from Git via .gitignore.
if exist "%MENU_DIR%\.env.bat" (
    call "%MENU_DIR%\.env.bat"
)

rem -- Run pre-command if defined ------------------------------------
rem    Example: set TOOLS_PRE_COMMAND=C:\path	o\.venv\Scriptsctivate.bat
if defined TOOLS_PRE_COMMAND (
    call "%TOOLS_PRE_COMMAND%"
)

rem -- Select Python interpreter ------------------------------------
rem    Set TOOLS_PYTHON if python is not in PATH.
rem    Example: set TOOLS_PYTHON=C:\Python311\python.exe
if not defined TOOLS_PYTHON set "TOOLS_PYTHON=python"

rem -- Launch menu --------------------------------------------------
"%TOOLS_PYTHON%" "%MENU_DIR%\menu.py"

endlocal
pause
