# Install writers-room into Claude Code, Codex CLI, and Gemini CLI
# by creating directory symlinks into each tool's user-scope skills folder.
# Safe to re-run: existing entries are skipped, not overwritten.
#
# Note: symlinks on Windows require Developer Mode (Settings > Privacy & security
# > For developers > Developer Mode) or running this script from an elevated shell.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillName = 'writers-room'

$targets = @(
    @{ Path = Join-Path $HOME ".claude\skills\$skillName"; Label = 'Claude Code' }
    @{ Path = Join-Path $HOME ".agents\skills\$skillName"; Label = 'Codex CLI'   }
    @{ Path = Join-Path $HOME ".gemini\skills\$skillName"; Label = 'Gemini CLI'  }
)

Write-Host "Linking $scriptDir into:"
foreach ($t in $targets) {
    $parent = Split-Path -Parent $t.Path
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if (Test-Path $t.Path) {
        Write-Host ("  [skip]   {0,-12} ->  {1}  (already exists)" -f $t.Label, $t.Path)
        continue
    }
    try {
        New-Item -ItemType SymbolicLink -Path $t.Path -Target $scriptDir | Out-Null
        Write-Host ("  [ok]     {0,-12} ->  {1}" -f $t.Label, $t.Path)
    } catch {
        Write-Host ("  [error]  {0,-12} ->  {1}" -f $t.Label, $_.Exception.Message)
        Write-Host "  Note: symlinks on Windows require Developer Mode or an elevated shell."
    }
}

Write-Host ""
Write-Host "Done. Restart your CLI so it discovers the skill."
