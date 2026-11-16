#!/usr/bin/env bash
# Installiert oder aktualisiert PanelAtlas auf Debian/Ubuntu (z. B. im Proxmox-LXC).
# Aufruf als root aus dem entpackten Paket:  bash install/setup.sh
# Daten liegen in /var/lib/verteiler und bleiben bei einem Update erhalten.
set -euo pipefail
PORT="${VERTEILER_PORT:-8080}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen."; exit 1; }

export DEBIAN_FRONTEND=noninteractive
# apt: Wiederholungen und Zeitlimit, damit ein hängender Spiegelserver nicht minutenlang blockiert.
# IPv4 wird erzwungen (kaputtes IPv6 ist die häufigste Ursache für hängende Downloads); mit VERTEILER_IPV6=1 abschaltbar.
APT_OPTS=(-o Acquire::Retries=3 -o Acquire::http::Timeout=25 -o Acquire::https::Timeout=25 -o Dpkg::Use-Pty=0)
[ "${VERTEILER_IPV6:-0}" = 1 ] || APT_OPTS+=(-o Acquire::ForceIPv4=true)
echo "==> [1/4] Paketlisten aktualisieren"
apt-get "${APT_OPTS[@]}" update
echo "==> [2/4] Systempakete installieren (Python, Cairo, Schriften, rclone)"
apt-get "${APT_OPTS[@]}" install -y --no-install-recommends python3 python3-venv python3-pip libcairo2 fonts-dejavu-core ca-certificates curl rclone

id verteiler >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/verteiler --shell /usr/sbin/nologin verteiler
mkdir -p /opt/verteiler /var/lib/verteiler
rm -rf /opt/verteiler/app
cp -r "$SRC/app" "$SRC/requirements.txt" /opt/verteiler/
find /opt/verteiler/app -name __pycache__ -type d -prune -exec rm -rf {} +
echo "==> [3/4] Python-Pakete installieren"
[ -d /opt/verteiler/venv ] || python3 -m venv /opt/verteiler/venv
/opt/verteiler/venv/bin/pip install --disable-pip-version-check --progress-bar off --timeout 30 --retries 3 -r /opt/verteiler/requirements.txt
chown -R verteiler:verteiler /var/lib/verteiler

echo "==> [4/4] Dienst einrichten und starten"
cat > /etc/systemd/system/verteiler.service <<UNIT
[Unit]
Description=PanelAtlas
After=network-online.target
Wants=network-online.target

[Service]
User=verteiler
Group=verteiler
WorkingDirectory=/opt/verteiler
Environment=VERTEILER_DATA=/var/lib/verteiler
ExecStart=/opt/verteiler/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
Restart=on-failure
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable -q verteiler
systemctl restart verteiler
sleep 2
systemctl is-active -q verteiler || { journalctl -u verteiler -n 30 --no-pager; echo "Dienst startet nicht."; exit 1; }
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Fertig. Weboberfläche: http://${IP:-<IP-des-Containers>}:${PORT}"
echo "Daten: /var/lib/verteiler   Dienst: systemctl status verteiler   Logs: journalctl -u verteiler"
