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

# ── 3. Create ~/.p-mon home directory ─────────────────────────────────────────
Write-Step "Setting up ~/.p-mon home..."
$pmonHome  = Join-Path $env:USERPROFILE '.p-mon'
$pmonBin   = Join-Path $pmonHome 'bin'
$pmonLogs  = Join-Path $pmonHome 'logs'
$pmonDocs  = Join-Path $pmonHome 'docs'
foreach ($dir in @($pmonBin, $pmonLogs, $pmonDocs)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}
Write-Ok "Created $pmonHome"

# ── 4. Write wrapper script ────────────────────────────────────────────────────
Write-Step "Writing wrapper script..."
$wrapper = Join-Path $pmonBin 'p-mon.cmd'
Set-Content -Path $wrapper -Value "@python -m project_monitor %*" -Encoding ASCII
Write-Ok "Wrapper: $wrapper"

# ── 5. Write quickstart doc ────────────────────────────────────────────────────
$doc = Join-Path $pmonDocs 'quickstart.md'
Set-Content -Path $doc -Encoding UTF8 -Value @'
# p-mon quick reference

## Scan
  p-mon                    # scan current directory
  p-mon ~/projects         # scan a specific folder
  p-mon --depth 3          # scan deeper (1-3, default 2)
  p-mon --compact          # one-line-per-repo view
  p-mon --local            # skip remote/GitHub details

## Tag & track
  p-mon --tag LABEL                    # tag current repo
  p-mon --tag LABEL --path DIR         # tag a specific repo
  p-mon --tag LABEL --folder DIR       # bulk-tag all repos in a folder
  p-mon --global                       # show all tagged projects
  p-mon --global --local               # show tags without running git

## Output
  p-mon --output report.txt            # export plain-text report
  p-mon --log-file debug.log           # write debug log to file
  p-mon --version                      # show version

## Data stored in ~/.p-mon/
  tags.json    tagged project registry
  logs/        rotating run log (pmon.log)
  docs/        this file
'@
Write-Ok "Quickstart: $doc"

# ── 6. Ensure ~/.p-mon\bin is on PATH ─────────────────────────────────────────
$userPath    = [string][Environment]::GetEnvironmentVariable('PATH', 'User')
$machinePath = [string][Environment]::GetEnvironmentVariable('PATH', 'Machine')
$combined    = "$userPath;$machinePath"

if ($combined -like "*$pmonBin*") {
    Write-Ok "Already on PATH"
} else {
    Write-Step "Adding $pmonBin to your user PATH..."
    $newPath = ($userPath.TrimEnd(';') + ';' + $pmonBin).TrimStart(';')
    [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
    Write-Ok "PATH updated"
    Write-Host ""
    Write-Warn "Restart your terminal for the PATH change to take effect."
}

Write-Host ""
Write-Host "  Done. Run:  p-mon" -ForegroundColor White
Write-Host ""
