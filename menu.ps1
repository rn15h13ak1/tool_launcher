# ================================================================
#  Tool Launcher - PowerShell launcher
#  Alternative to menu.bat for environments where .bat is restricted.
#
#  Usage:
#    Right-click -> "Run with PowerShell"
#    or from PowerShell terminal:
#      powershell -ExecutionPolicy Bypass -File "C:\path\to\menu.ps1"
# ================================================================

# Directory of this script (ws\tool_launcher\)
$MenuDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ----------------------------------------------------------------
# Load .env.ps1 if it exists
# Copy .env.ps1.example to .env.ps1 and edit for your environment.
# .env.ps1 is excluded from Git via .gitignore.
# ----------------------------------------------------------------
$EnvFile = Join-Path $MenuDir ".env.ps1"
if (Test-Path $EnvFile) {
    . $EnvFile
}

# ----------------------------------------------------------------
# Run pre-command if defined
# Example in .env.ps1:
#   $env:TOOLS_PRE_COMMAND = "C:\path\to\.venv\Scripts\activate.bat"
# ----------------------------------------------------------------
if ($env:TOOLS_PRE_COMMAND) {
    cmd /c $env:TOOLS_PRE_COMMAND
}

# ----------------------------------------------------------------
# Select Python interpreter
# Set TOOLS_PYTHON in .env.ps1 if python is not in PATH.
# Example: $env:TOOLS_PYTHON = "C:\Python311\python.exe"
# ----------------------------------------------------------------
if (-not $env:TOOLS_PYTHON) {
    $env:TOOLS_PYTHON = "python"
}

# ----------------------------------------------------------------
# Launch menu
# ----------------------------------------------------------------
$MenuScript = Join-Path $MenuDir "menu.py"
& $env:TOOLS_PYTHON $MenuScript

Write-Host ""
Write-Host "Press Enter to exit..." -NoNewline
Read-Host
