#!/usr/bin/env sh
# Checks what MrCourt needs on this machine (macOS, Linux, Git Bash). Run from the repository root:
#   sh scripts/check-prerequisites.sh
# Exit code 0 = everything required is present; 1 = something required is missing. Optional items only warn.

missing=0
ok()   { printf '[ok]   %-34s %s\n' "$1" "$2"; }
miss() { printf '[MISS] %-34s %s\n' "$1" "$2"; missing=$((missing + 1)); }
warn() { printf '[warn] %-34s %s\n' "$1" "$2"; }

# Python 3.12+
PY=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
if [ -n "$PY" ] && "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
  ok "Python 3.12 or newer" "$("$PY" --version 2>&1)"
else
  miss "Python 3.12 or newer" "not found or too old (install from python.org)"
fi

# Node.js 22+ and npm
if command -v node >/dev/null 2>&1; then
  major=$(node --version | sed 's/^v//; s/\..*//')
  if [ "$major" -ge 22 ] 2>/dev/null; then ok "Node.js 22 or newer" "$(node --version)"; else miss "Node.js 22 or newer" "found $(node --version)"; fi
  command -v npm >/dev/null 2>&1 && ok "npm" "$(npm --version)" || miss "npm" "comes with Node.js"
else
  miss "Node.js 22 or newer" "not found (install from nodejs.org)"
fi

# Docker, with the engine running (PostgreSQL runs in it)
if command -v docker >/dev/null 2>&1; then
  ok "Docker" "$(docker --version)"
  docker info >/dev/null 2>&1 && ok "Docker engine running" "" || miss "Docker engine running" "start Docker Desktop"
  docker compose version >/dev/null 2>&1 && ok "Docker Compose" "" || miss "Docker Compose" "comes with Docker Desktop"
else
  miss "Docker Desktop" "not found (needed for the PostgreSQL database)"
fi

# Git
command -v git >/dev/null 2>&1 && ok "Git" "$(git --version)" || miss "Git" "not found (install from git-scm.com)"

# Chrome or Edge (voice control needs the browser's speech recognition)
found=""
for b in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge msedge; do
  command -v "$b" >/dev/null 2>&1 && { found="$b"; break; }
done
for p in "/Applications/Google Chrome.app" "/Applications/Microsoft Edge.app" \
         "/c/Program Files/Google/Chrome/Application/chrome.exe" "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"; do
  [ -e "$p" ] && { found="$p"; break; }
done
[ -n "$found" ] && ok "Chrome or Edge" "$found" || miss "Chrome or Edge" "not found (voice control needs one of them)"

# A microphone (best effort: the browser still asks for permission when voice control is turned on)
if command -v arecord >/dev/null 2>&1 && arecord -l 2>/dev/null | grep -q 'card'; then ok "Microphone (for voice control)" "detected"
else warn "Microphone (for voice control)" "could not detect one here; the browser will ask when you turn voice control on"; fi

command -v tesseract >/dev/null 2>&1 && ok "Tesseract (optional)" "" || warn "Tesseract (scanned PDFs, optional)" "only needed to read scans"
[ -f backend/.env ] && ok "backend/.env" "" || warn "backend/.env" "copy .env.example to backend/.env and fill in what you use"

echo
if [ "$missing" -eq 0 ]; then echo "Everything required is present."; exit 0; fi
echo "$missing required item(s) missing. See 'Prerequisites' in README.md."
exit 1
