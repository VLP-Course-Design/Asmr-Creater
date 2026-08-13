$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if ($env:PLAYBACK_PYTHON) {
  $pythonExe = $env:PLAYBACK_PYTHON
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $pythonExe = (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $pythonExe = (Get-Command py).Source
} else {
  throw 'Python was not found. Install Python 3.10+ or set PLAYBACK_PYTHON to python.exe.'
}

$converter = "$repoRoot\src\audio\playback_converter.py"
$examples = "$repoRoot\contracts\playback_proposal\examples"

& $pythonExe $converter `
  "$examples\with_depth\example_coastal_bird_with_depth.json" `
  --output-dir "$repoRoot\outputs\playback\with_depth" `
  --seed 18432 `
  --duration 1800

& $pythonExe $converter `
  "$examples\without_depth\example_study_keyboard_without_depth.json" `
  --output-dir "$repoRoot\outputs\playback\without_depth" `
  --seed 18432 `
  --duration 1800

Write-Host "Demo completed. Outputs: $repoRoot\outputs\playback"
