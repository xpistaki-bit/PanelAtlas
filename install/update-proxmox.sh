#!/usr/bin/env bash
# Updates the app in an existing container. Data in /var/lib/verteiler is kept.
# On the Proxmox host as root, straight from GitHub:
#   CTID=109 bash -c "$(curl -fsSL https://raw.githubusercontent.com/xpistaki-bit/PanelAtlas/main/install/update-proxmox.sh)"
# or from the unpacked repository:
#   CTID=109 bash install/update-proxmox.sh
set -euo pipefail
: "${CTID:?Please pass CTID=<container id>}"
command -v pct >/dev/null || { echo "This script must run on the Proxmox host (pct not found)."; exit 1; }
REPO="${REPO:-xpistaki-bit/PanelAtlas}"
BRANCH="${BRANCH:-main}"
# Source: the unpacked repository next to this script, or a download from GitHub when run via curl.
SELF="${BASH_SOURCE[0]:-}"
if [ -n "$SELF" ] && [ -f "$SELF" ] && [ -d "$(dirname "$SELF")/../app" ]; then
  SRC="$(cd "$(dirname "$SELF")/.." && pwd)"
else
  SRC="$(mktemp -d /tmp/verteiler-src-XXXXXX)"
  URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"
  echo "==> Downloading $URL"
  if command -v curl >/dev/null; then curl -fsSL "$URL" -o "$SRC/src.tar.gz"; else wget -qO "$SRC/src.tar.gz" "$URL"; fi
  tar -xzf "$SRC/src.tar.gz" -C "$SRC" --strip-components=1 && rm -f "$SRC/src.tar.gz"
  [ -d "$SRC/app" ] || { echo "Download incomplete: $URL"; exit 1; }
fi
TMP="$(mktemp /tmp/verteiler-XXXXXX.tar.gz)"
tar -C "$SRC" --exclude=data --exclude=__pycache__ --exclude=.git -czf "$TMP" .
pct exec "$CTID" -- sh -c 'rm -rf /root/verteiler-paket && mkdir -p /root/verteiler-paket'
pct push "$CTID" "$TMP" /root/verteiler-paket.tar.gz
rm -f "$TMP"
pct exec "$CTID" -- tar -C /root/verteiler-paket -xzf /root/verteiler-paket.tar.gz
pct exec "$CTID" -- env VERTEILER_IPV6="${VERTEILER_IPV6:-0}" bash /root/verteiler-paket/install/setup.sh
