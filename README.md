# PanelAtlas – distribution board documentation

A small web app for documenting electrical distribution boards true to scale: pick an enclosure, populate the
DIN rails, label the circuits, print a PDF, generate 1:1 label strips and export CSV. It runs as a single
service with an SQLite file, either in a Proxmox LXC or in a Docker container. The interface is available in
German and English (switch at the top right).

The standards notes in the app are a plausibility aid. They do not replace planning or inspection by a
qualified electrician.
<img width="1138" height="1544" alt="Verteilerkasten1" src="https://github.com/user-attachments/assets/50d5793e-5391-4254-b447-612c4ab1e4de" />

<img width="1632" height="1460" alt="Device_configuration" src="https://github.com/user-attachments/assets/42ed4886-d7f0-472e-831e-edc34057916d" />

## Installation

There are two supported ways to run the app. Both serve the web interface on port 8080.

### Option 1: Proxmox LXC

Run this on the Proxmox host as root:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/xpistaki-bit/PanelAtlas/main/install/install-proxmox.sh)"
```

The script creates an unprivileged Debian 12 container, installs the app and prints the address at the end,
for example `http://192.168.xxx.xxx:8080`.

Defaults: next free container ID, storage picked automatically (`local-lvm` or `local-zfs` if present),
bridge `vmbr0`, DHCP, 4 GB disk, 512 MB RAM, port 8080. Override them with variables:

```bash
CTID=120 STORAGE=local-zfs IP=192.168.xxx.xxx/24 GW=192.168.1.1 \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/xpistaki-bit/PanelAtlas/main/install/install-proxmox.sh)"
```

| Variable | Meaning | Default |
|---|---|---|
| `CTID` | container ID | next free ID |
| `NAME` | hostname | `panelatlas` |
| `STORAGE` | storage for the container disk | automatic |
| `TPL_STORAGE` | storage for the Debian template | automatic |
| `BRIDGE` | network bridge | `vmbr0` |
| `IP`, `GW` | static address (CIDR) and gateway | DHCP |
| `DISK`, `RAM`, `CORES` | disk in GB, memory in MB, CPU cores | 4, 512, 1 |
| `VERTEILER_PORT` | port of the web interface | 8080 |
| `VERTEILER_IPV6=1` | let apt use IPv6 (IPv4 is forced by default, because broken IPv6 is the usual cause of hanging downloads) | off |

**Update** (data is kept):

```bash
CTID=120 bash -c "$(curl -fsSL https://raw.githubusercontent.com/xpistaki-bit/PanelAtlas/main/install/update-proxmox.sh)"
```

Without GitHub access, clone or unpack the repository on the host and run `bash install/install-proxmox.sh`
or `CTID=120 bash install/update-proxmox.sh` from its folder. On any other Debian or Ubuntu machine (VM, bare
metal), run `bash install/setup.sh` as root.

| What | Where |
|---|---|
| Program | `/opt/verteiler` |
| Data (database, images) | `/var/lib/verteiler` |
| Service | `systemctl status verteiler`, logs: `journalctl -u verteiler` |
| Shell in the container | on the host: `pct enter <CTID>` (no password needed) |

### Option 2: Docker

Requirements: Docker Engine with the Compose plugin.

```bash
git clone https://github.com/xpistaki-bit/PanelAtlas.git
cd PanelAtlas
docker compose up -d --build
```

The interface is then available at `http://<docker-host>:8080`. All data lives in the named volume
`verteiler-data` (mounted at `/data` in the container).

| Task | Command |
|---|---|
| Update | `git pull && docker compose up -d --build` |
| Logs | `docker compose logs -f` |
| Stop / start | `docker compose stop` / `docker compose start` |
| Back up the data volume | `docker run --rm -v verteiler-data:/data -v "$PWD":/out alpine tar czf /out/verteiler-data.tgz -C /data .` |

To use another port, change the left number of `8080:8080` in `docker-compose.yml`. To use the "Folder / NAS"
backup target, uncomment the second volume line in `docker-compose.yml` and enter `/backup` in the app.
For rclone, run `docker compose exec panelatlas rclone config` once; the configuration is stored in the
data volume.

Without Compose:

```bash
docker build -t panelatlas .
docker run -d --name panelatlas --restart unless-stopped -p 8080:8080 -v verteiler-data:/data panelatlas
```

## Using the app

- **Profiles** group configurations, for example per house or per customer. A password per profile is optional.
- **New configuration:** give it a name and pick the enclosure (filter by manufacturer and mounting type).
- **Populate:** click a DIN rail to choose the target row, then click a device in the list on the left. Devices
  can be dragged, also between rows; the arrow keys move the selected device, Delete removes it. In the device
  list the colour shows the number of poles: blue 1-pole, green 2-pole, orange 3-pole, violet 4-pole.
- **Label:** designation, function and room per device. The label is shown below the device, in the printout
  and in the CSV. The label font size is adjustable per configuration (enclosure tab, 100 % to 200 %) and
  applies to the view and the PDF.
- **Mark:** a placed device can get a bright marker (red, yellow, magenta, cyan), for example when it causes
  trouble or its purpose is unclear. The label field can be coloured in twelve colours. For breakers, "2 wires"
  adds a `2×` marker on the device.
- **Phases:** breakers placed after a 3- or 4-pole RCD are assigned to L1, L2, L3 in turn (3-pole breakers get
  L1-L3). The option is on by default and can be switched off per RCD.
- **Copy from another configuration:** the enclosure tab has "Copy devices from …". Choose the source, all
  rows or single rows, the target rows and whether existing devices are replaced or kept.
- **Check:** overfilled rows are errors. Standards notes (DIN VDE 0100-410/-443/-530, DIN 18015) never block
  anything; each one can be ticked as a deliberate deviation and is then printed as such. The notes can be
  switched off per configuration.
- **Output:** PDF, CSV (all columns), **CSV light** (row, position, function, room only), SVG and JSON. "Print
  / PDF" asks what the PDF should contain: overview, enlarged detail pages, circuit list, and check results
  with notes.

### Meters

The category **Meters** contains a digital meter (mME, eHZ plug-in and three-point mounting), a conventional
Ferraris meter (kME) and a smart metering system (iMSys: mME plus smart meter gateway). A meter is taller than
one row: it hangs in its row and covers the rows below it. Rows covered by a meter must stay empty, otherwise
the check reports an error.

### PE/N terminal blocks

Most enclosures carry PE and N terminal blocks at the top, at the bottom or in the middle. They are drawn in
the enclosure view (green PE, blue N). The positions are set per enclosure in the catalog and can be changed
per configuration in the enclosure tab. The default is top and bottom. A block can also be clicked in the view
and removed with the Delete key.

### Label strips

**Labels** in the editor creates a PDF at 1:1 scale: one strip per populated row, each cell as wide as its
device. Module width (17.5 / 17.8 / 18 / 18.5 mm), height, font size, orientation, cutting frame and content
(designation, function, room, rated current, phase as a colour bar) are adjustable. Print at 100 %, not "fit
to page"; the 100 mm bar on the sheet is there to check the scale.

## Catalog

The starter catalog contains small distribution boards from ABB (ComfortLine Compact CA/CU, UK600), Hager
(volta, univers) and Schneider (Resi9 KV); modular devices from Hager, ABB and Schneider; surge arresters from
DEHN and Hager; Phoenix Contact terminal blocks; main-line branch terminals from Hager and f-tronic; and
meters. Article names in the catalog are stored in German.

- **verified** (geprüft): dimensions or article numbers checked against manufacturer documents.
- **unverified** (ungeprüft): created from the DIN 43880 grid (1 module = 17.5 mm) or from typical values.
  Check against the data sheet before relying on the dimension. This applies mainly to ABB and Schneider
  devices, terminal lengths and the meters with three-point mounting.

Own enclosures and devices: **Catalog → Own entry**. Width is entered in mm (1 module = 17.5 mm).

### CSV import and export

**Catalog → Import CSV** reads one row per article (separator `;` or `,`). Existing articles (same
manufacturer and article number) are updated. A template with all columns is available under "Download CSV
template". Required: `article` and a width (`width_mm` or `width_te`); enclosures also need `height_mm` and
`rows`. German column names are recognised. A column `image_url` stores the image address.

### BMEcat / ETIM

**Catalog → Import BMEcat / ETIM** reads a manufacturer's catalog file (XML or ZIP, BMEcat 2005). The app
detects the ETIM class per product, shows an overview and imports only classes that belong in a distribution
board. Width in modules, number of poles, rated current, tripping characteristic and residual current come
from the ETIM features; image addresses in the file are kept.

| ETIM class | Type | Status |
|---|---|---|
| EC000042 miniature circuit breaker | MCB | features verified |
| EC000003 residual current circuit breaker | RCD | features verified |
| EC000897 terminal block | terminal | class verified, dimensions from width/height |
| EC000214 small distribution board | enclosure | class verified, check row spacing and mounting |
| EC000905, EC000941 | RCBO, surge protection | suggestion, marked unverified |

Further classes can be mapped in the import dialog, for example `EC001234=switch`.

None of the manufacturers offers a freely accessible online interface. The files are obtained like this:

- **Phoenix Contact:** create and download a BMEcat (with ETIM and ECLASS, including image links) in the
  customer account "My Phoenix Contact".
- **ABB / Striebel & John:** BMEcat with ETIM as a download in the ABB library.
- **Hager, Schneider Electric, DEHN:** via customer portal, wholesaler or on request.

### Device graphics

How a device is drawn depends on its type; a small designer in the catalog entry sets the actuator, circuit
symbol, print and label window, and an image replaces the drawing. See
[docs/device-graphics.md](docs/device-graphics.md).

### Manufacturer images

Manufacturer photos are protected by copyright and are not part of this repository. Under **Catalog → Edit**
an image can be uploaded per article or loaded from an image address (BMEcat imports usually fill it in). The
image is stretched to the real device dimensions; without an image the app draws the device to scale.

## Backup

Targets are configured under **Settings**. Each backup is a ZIP file with all profiles, configurations, own
catalog entries, images, and a PDF and CSV per configuration.

- **Folder / NAS:** a path in the container, for example a directory mounted from Proxmox
  (`pct set <CTID> -mp0 /mnt/pve/nas/verteiler,mp=/mnt/sicherung`) or a Docker volume. The user `verteiler`
  needs write access.
- **WebDAV:** for example Nextcloud: `https://cloud.example.com/remote.php/dav/files/NAME/Verteiler`, user and
  app password.
- **rclone** (Google Drive, OneDrive, Dropbox, S3 and others): run `runuser -u verteiler -- rclone config` once
  in the LXC and enter the remote in the app, for example `gdrive:Verteiler`.

Optionally the app backs up automatically once a day when something has changed.

## Access protection

- Profile password: protects viewing, changing and exporting the configurations of that profile.
- Admin password (Settings): protects the catalog, imports, backup targets and the full backup.
- The app speaks plain HTTP. For access from outside the local network, put a reverse proxy with TLS in front.
- Configured backup targets also receive the data of password-protected profiles.

## Version

The running version is shown at the top right of the interface, next to a link to this repository. After an
update the browser loads the new interface automatically; if it still shows the old one, reload with
Ctrl+F5 once.

## Technology

Python 3.11+, FastAPI, SQLite, server-side SVG (1 unit = 1 mm), PDF via CairoSVG. No build step; the interface
is plain HTML and JavaScript. Translations live in `app/static/i18n.js` (interface) and in the tables in
`app/checks.py` and `app/export.py` (notes, PDF, CSV). The starter catalog is generated by `tools/seed.py`.
The version number lives in `app/version.py`.
