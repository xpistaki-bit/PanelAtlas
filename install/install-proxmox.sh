#!/usr/bin/env bash
# Creates a Debian 12 LXC on a Proxmox VE host and installs PanelAtlas in it.
# Run as root on the Proxmox host, either straight from GitHub:
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/xpistaki-bit/PanelAtlas/main/install/install-proxmox.sh)"
# or from the unpacked repository:
#   bash install/install-proxmox.sh
# Adjustable through environment variables, for example:
#   CTID=120 STORAGE=local-zfs BRIDGE=vmbr0 IP=192.168.1.50/24 GW=192.168.1.1 bash install/install-proxmox.sh
set -euo pipefail
command -v pct >/dev/null || { echo "This script must run on the Proxmox host (pct not found)."; exit 1; }
[ "$(id -u)" = 0 ] || { echo "Please run as root."; exit 1; }

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
CTID="${CTID:-$(pvesh get /cluster/nextid)}"
NAME="${NAME:-panelatlas}"
STORAGE="${STORAGE:-}"
TPL_STORAGE="${TPL_STORAGE:-}"
BRIDGE="${BRIDGE:-vmbr0}"
DISK="${DISK:-4}"
RAM="${RAM:-512}"
CORES="${CORES:-1}"
IP="${IP:-dhcp}"
GW="${GW:-}"
PORT="${VERTEILER_PORT:-8080}"

if pct status "$CTID" >/dev/null 2>&1; then echo "Container $CTID already exists. Please pass CTID=..."; exit 1; fi

# Pick the storage automatically: prefer local-lvm / local-zfs, otherwise the first active suitable one
pick_storage() {  # $1 = Inhaltstyp (rootdir | vztmpl)
  local list; list="$(pvesm status -content "$1" 2>/dev/null | awk 'NR>1 && $3=="active" {print $1}')"
  for s in local-lvm local-zfs local; do echo "$list" | grep -qx "$s" && { echo "$s"; return; }; done
  echo "$list" | head -1
}
[ -n "$STORAGE" ] || STORAGE="$(pick_storage rootdir)"
[ -n "$TPL_STORAGE" ] || TPL_STORAGE="$(pick_storage vztmpl)"
[ -n "$STORAGE" ] || { echo "No storage for containers found (pvesm status -content rootdir)."; exit 1; }
[ -n "$TPL_STORAGE" ] || { echo "No storage for templates found (pvesm status -content vztmpl)."; exit 1; }
if ! pvesm status -content rootdir | awk 'NR>1 {print $1}' | grep -qx "$STORAGE"; then
  echo "Storage '$STORAGE' cannot hold containers. Available:"; pvesm status -content rootdir; exit 1
fi
echo "==> Storage: container on '$STORAGE', template on '$TPL_STORAGE'"

echo "==> Looking for the Debian 12 template"
pveam update >/dev/null
TPL="$(pveam available --section system | awk '/debian-12-standard/ {print $2}' | sort -V | tail -1)"
[ -n "$TPL" ] || { echo "No Debian 12 template found."; exit 1; }
pveam list "$TPL_STORAGE" | grep -q "$TPL" || pveam download "$TPL_STORAGE" "$TPL"

NET="name=eth0,bridge=${BRIDGE},ip=${IP}"
[ -n "$GW" ] && NET="${NET},gw=${GW}"

echo "==> Creating container $CTID ($NAME)"
pct create "$CTID" "${TPL_STORAGE}:vztmpl/${TPL}" --hostname "$NAME" --cores "$CORES" --memory "$RAM" --swap 256 \
  --rootfs "${STORAGE}:${DISK}" --net0 "$NET" --unprivileged 1 --features nesting=1 --onboot 1 \
  --description "PanelAtlas, Port ${PORT}"
pct start "$CTID"

echo "==> Waiting for the network"
for i in $(seq 1 40); do
  pct exec "$CTID" -- sh -c 'getent hosts deb.debian.org >/dev/null 2>&1' && break
  sleep 2
  [ "$i" = 40 ] && { echo "The container has no network (check DNS/DHCP)."; exit 1; }
done

echo "==> Transferring and installing the app"
TMP="$(mktemp /tmp/verteiler-XXXXXX.tar.gz)"
tar -C "$SRC" --exclude=data --exclude=__pycache__ --exclude=.git -czf "$TMP" .
pct exec "$CTID" -- mkdir -p /root/verteiler-paket
pct push "$CTID" "$TMP" /root/verteiler-paket.tar.gz
rm -f "$TMP"
pct exec "$CTID" -- tar -C /root/verteiler-paket -xzf /root/verteiler-paket.tar.gz
pct exec "$CTID" -- env VERTEILER_PORT="$PORT" VERTEILER_IPV6="${VERTEILER_IPV6:-0}" bash /root/verteiler-paket/install/setup.sh

echo
echo "Container $CTID is running. To update later, run on the Proxmox host:"
echo "  CTID=$CTID bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/install/update-proxmox.sh)\""
echo "Shell in the container without a password:  pct enter $CTID"
