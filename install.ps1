#Requires -Version 5.1
<#
.SYNOPSIS
    Installs pmon-cli and ensures p-mon is on your PATH.
.DESCRIPTION
    Runs pip install, finds where pip placed the script, and permanently
    adds that directory to your user PATH if it is not already there.
    Restart your terminal after running this script.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step { param([string]$msg) Write-Host "  > $msg" -ForegroundColor Cyan }
function Write-Ok   { param([string]$msg) Write-Host "  + $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  ! $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  pmon-cli installer" -ForegroundColor White
Write-Host "  ------------------" -ForegroundColor DarkGray
Write-Host ""

# ── 1. Locate Python ──────────────────────────────────────────────────────────
Write-Step "Locating Python..."
$python = $null
foreach ($cmd in @('python', 'python3', 'py')) {
    try {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) { $python = $cmd; break }
    } catch {}
}
if (-not $python) {
    Write-Host "`n  Error: Python not found. Install it from https://python.org" -ForegroundColor Red
    exit 1
}
$pyVer = & $python --version 2>&1
Write-Ok "Found $pyVer"

# ── 2. Install pmon-cli ───────────────────────────────────────────────────────
Write-Step "Installing pmon-cli (pip)..."
& $python -m pip install --upgrade pmon-cli
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n  Error: pip install failed." -ForegroundColor Red
    exit 1
}
Write-Ok "pmon-cli installed"

# ── 3. Find scripts directory ─────────────────────────────────────────────────
Write-Step "Locating scripts directory..."
$scriptsDir = & $python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
if (-not $scriptsDir -or -not (Test-Path $scriptsDir)) {
    Write-Warn "Could not confirm scripts directory: $scriptsDir"
    Write-Warn "Run 'python -m project_monitor' as a fallback."
    exit 0
}
Write-Ok "Scripts: $scriptsDir"

# ── 4. Ensure directory is on PATH ────────────────────────────────────────────
$userPath    = [string][Environment]::GetEnvironmentVariable('PATH', 'User')
$machinePath = [string][Environment]::GetEnvironmentVariable('PATH', 'Machine')
$combined    = "$userPath;$machinePath"

if ($combined -like "*$scriptsDir*") {
    Write-Ok "Already on PATH"
} else {
    Write-Step "Adding $scriptsDir to your user PATH..."
    $newPath = ($userPath.TrimEnd(';') + ';' + $scriptsDir).TrimStart(';')
    [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
    Write-Ok "PATH updated"
    Write-Host ""
    Write-Warn "Restart your terminal for the PATH change to take effect."
}

Write-Host ""
Write-Host "  Done. Run:  p-mon" -ForegroundColor White
Write-Host ""
