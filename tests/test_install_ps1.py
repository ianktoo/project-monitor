"""Tests for install.ps1: PS 5.1 compatibility and PATH manipulation logic."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

INSTALLER = Path(__file__).parent.parent / "install.ps1"

_win = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def _ps51(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-Version", "5.1", "-NonInteractive", "-NoProfile",
         "-Command", script],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Static checks — no process required


def test_installer_exists():
    assert INSTALLER.exists()


@pytest.mark.parametrize("pattern,label", [
    (r"\?\?", "null-coalescing ??"),
    (r"\?\.", "null-conditional ?."),
])
def test_no_ps7_operators(pattern: str, label: str):
    """PS 7+ operators must not appear on non-comment lines."""
    violations = [
        f"line {i + 1}: {line.rstrip()}"
        for i, line in enumerate(INSTALLER.read_text(encoding="utf-8").splitlines())
        if re.search(pattern, line) and not line.lstrip().startswith("#")
    ]
    assert not violations, f"PS 7+ operator '{label}' found:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# PS 5.1 parse check


@_win
def test_ps51_parses_cleanly():
    """install.ps1 must have zero parse errors under Windows PowerShell 5.1."""
    path = str(INSTALLER).replace("\\", "/")
    script = (
        "$tokens = $null\n"
        "$errors = $null\n"
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$tokens, [ref]$errors)\n"
        "exit $errors.Count"
    )
    result = _ps51(script)
    assert result.returncode == 0, (
        f"install.ps1 has {result.returncode} syntax error(s) under PS 5.1:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# PATH manipulation logic


@_win
def test_string_cast_converts_null_to_empty():
    """[string]$null must produce '' — the fix that replaced ?? ''."""
    result = _ps51("$v = [string]$null; if ($v -eq '') { exit 0 } else { exit 1 }")
    assert result.returncode == 0, "[string]$null did not produce empty string"


@_win
def test_path_already_present_no_update(tmp_path: Path):
    """When scriptsDir is already in PATH, the script branch must say 'Already on PATH'."""
    scripts_dir = str(tmp_path / "Scripts").replace("\\", "/")
    script = (
        f"$userPath   = '{scripts_dir}'\n"
        f"$machinePath = ''\n"
        f"$scriptsDir  = '{scripts_dir}'\n"
        "$combined = \"$userPath;$machinePath\"\n"
        "if ($combined -like \"*$scriptsDir*\") { Write-Output 'Already on PATH' } "
        "else { Write-Output 'PATH updated' }"
    )
    result = _ps51(script)
    assert "Already on PATH" in result.stdout


@_win
def test_path_new_dir_appended(tmp_path: Path):
    """When scriptsDir is absent from PATH, it must be appended to userPath."""
    scripts_dir = str(tmp_path / "Scripts").replace("\\", "/")
    existing = "C:/Windows/System32"
    script = (
        f"$userPath   = '{existing}'\n"
        f"$scriptsDir = '{scripts_dir}'\n"
        "$newPath = ($userPath.TrimEnd(';') + ';' + $scriptsDir).TrimStart(';')\n"
        "Write-Output $newPath"
    )
    result = _ps51(script)
    assert existing in result.stdout
    assert scripts_dir in result.stdout


@_win
def test_path_empty_user_path_no_leading_semicolon(tmp_path: Path):
    """When userPath is '', the result must be just scriptsDir (no leading semicolon)."""
    scripts_dir = str(tmp_path / "Scripts").replace("\\", "/")
    script = (
        "$userPath   = [string]$null\n"
        f"$scriptsDir = '{scripts_dir}'\n"
        "$newPath = ($userPath.TrimEnd(';') + ';' + $scriptsDir).TrimStart(';')\n"
        "Write-Output $newPath"
    )
    result = _ps51(script)
    output = result.stdout.strip()
    assert output == scripts_dir, f"Expected '{scripts_dir}', got '{output}'"
    assert not output.startswith(";"), "PATH must not start with a semicolon"
