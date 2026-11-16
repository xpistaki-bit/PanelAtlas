#!/usr/bin/env bash
# Aktualisiert die App in einem bestehenden Container. Daten in /var/lib/verteiler bleiben erhalten.
# Auf dem Proxmox-Host als root, direkt von GitHub:
#   CTID=109 bash -c "$(curl -fsSL https://raw.githubusercontent.com/xpistaki-bit/PanelAtlas/main/install/update-proxmox.sh)"
# oder aus dem entpackten Paket:
#   CTID=109 bash install/update-proxmox.sh
set -euo pipefail
: "${CTID:?Bitte CTID=<Container-ID> angeben}"
command -v pct >/dev/null || { echo "Dieses Skript muss auf dem Proxmox-Host laufen (pct fehlt)."; exit 1; }
REPO="${REPO:-xpistaki-bit/PanelAtlas}"
BRANCH="${BRANCH:-main}"
# Quelle: das entpackte Paket neben diesem Skript – oder, beim Aufruf per curl, ein Download von GitHub.
SELF="${BASH_SOURCE[0]:-}"
if [ -n "$SELF" ] && [ -f "$SELF" ] && [ -d "$(dirname "$SELF")/../app" ]; then
  SRC="$(cd "$(dirname "$SELF")/.." && pwd)"
else
  SRC="$(mktemp -d /tmp/verteiler-src-XXXXXX)"
  URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"
  echo "==> Lade $URL"
  if command -v curl >/dev/null; then curl -fsSL "$URL" -o "$SRC/src.tar.gz"; else wget -qO "$SRC/src.tar.gz" "$URL"; fi
  tar -xzf "$SRC/src.tar.gz" -C "$SRC" --strip-components=1 && rm -f "$SRC/src.tar.gz"
  [ -d "$SRC/app" ] || { echo "Download unvollständig: $URL"; exit 1; }
fi
TMP="$(mktemp /tmp/verteiler-XXXXXX.tar.gz)"
tar -C "$SRC" --exclude=data --exclude=__pycache__ --exclude=.git -czf "$TMP" .
pct exec "$CTID" -- sh -c 'rm -rf /root/verteiler-paket && mkdir -p /root/verteiler-paket'
pct push "$CTID" "$TMP" /root/verteiler-paket.tar.gz
rm -f "$TMP"
pct exec "$CTID" -- tar -C /root/verteiler-paket -xzf /root/verteiler-paket.tar.gz
pct exec "$CTID" -- env VERTEILER_IPV6="${VERTEILER_IPV6:-0}" bash /root/verteiler-paket/install/setup.sh
