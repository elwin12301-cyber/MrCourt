# Checks what MrCourt needs on this machine (Windows). Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File scripts/check-prerequisites.ps1
# Exit code 0 = everything required is present; 1 = something required is missing. Optional items only warn.

$missing = 0

function Show($ok, $name, $detail, $required = $true) {
  if ($ok) { Write-Host ("[ok]   {0,-34} {1}" -f $name, $detail) -ForegroundColor Green }
  elseif ($required) { Write-Host ("[MISS] {0,-34} {1}" -f $name, $detail) -ForegroundColor Red; $script:missing++ }
  else { Write-Host ("[warn] {0,-34} {1}" -f $name, $detail) -ForegroundColor Yellow }
}

function Version-Of($command, $arguments) {
  try { return ((& $command $arguments 2>&1) | Out-String).Trim() } catch { return $null }
}

# Python 3.12+
$py = $null
foreach ($candidate in 'python', 'py') {
  if (Get-Command $candidate -ErrorAction SilentlyContinue) { $py = $candidate; break }
}
if ($py) {
  $text = Version-Of $py '--version'
  $ok = $text -match 'Python (\d+)\.(\d+)' -and ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 12))
  Show $ok 'Python 3.12 or newer' "$text"
} else { Show $false 'Python 3.12 or newer' 'not found (install from python.org)' }

# Node.js 22+ and npm
if (Get-Command node -ErrorAction SilentlyContinue) {
  $text = Version-Of node '--version'
  $ok = $text -match 'v(\d+)' -and [int]$Matches[1] -ge 22
  Show $ok 'Node.js 22 or newer' "$text"
  Show ([bool](Get-Command npm -ErrorAction SilentlyContinue)) 'npm' (Version-Of npm '--version')
} else { Show $false 'Node.js 22 or newer' 'not found (install from nodejs.org)' }

# Docker Desktop, with the engine running (PostgreSQL runs in it)
if (Get-Command docker -ErrorAction SilentlyContinue) {
  Show $true 'Docker' (Version-Of docker '--version')
  docker info *> $null
  Show ($LASTEXITCODE -eq 0) 'Docker engine running' 'start Docker Desktop and wait for the whale icon to settle'
  docker compose version *> $null
  Show ($LASTEXITCODE -eq 0) 'Docker Compose' 'comes with Docker Desktop'
} else { Show $false 'Docker Desktop' 'not found (install Docker Desktop for the PostgreSQL database)' }

# Git
if (Get-Command git -ErrorAction SilentlyContinue) { Show $true 'Git' (Version-Of git '--version') }
else { Show $false 'Git' 'not found (install from git-scm.com)' }

# Chrome or Edge (voice control needs the browser's speech recognition)
$browsers = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ }
Show ($browsers.Count -gt 0) 'Chrome or Edge' $(if ($browsers.Count) { Split-Path $browsers[0] -Leaf } else { 'not found (voice control needs one of them)' })

# A microphone (best effort: the browser still asks for permission when voice control is turned on)
$mic = $null
try { $mic = Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction Stop | Where-Object { $_.FriendlyName -match 'Microphone|Mic|Headset|Array' } } catch { }
Show ([bool]$mic) 'Microphone (for voice control)' $(if ($mic) { @($mic)[0].FriendlyName } else { 'none detected; voice control needs one' }) $false

# Optional: Tesseract for scanned PDFs
Show ([bool](Get-Command tesseract -ErrorAction SilentlyContinue)) 'Tesseract (scanned PDFs, optional)' 'only needed to read scans' $false

# Settings file
Show (Test-Path 'backend/.env') 'backend/.env' 'copy .env.example to backend/.env and fill in what you use' $false

Write-Host ''
if ($missing -eq 0) { Write-Host 'Everything required is present.' -ForegroundColor Green; exit 0 }
Write-Host "$missing required item(s) missing. See 'Prerequisites' in README.md." -ForegroundColor Red
exit 1
