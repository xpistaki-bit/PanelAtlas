"""Sicherung: ZIP mit allen Daten -> lokaler Ordner / WebDAV / rclone."""
import datetime
import io
import json
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

import httpx

from . import export


def build_zip(db, media_dir, with_documents=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        profiles = [dict(r) for r in db.execute("SELECT * FROM profiles")]
        configs = [dict(r) for r in db.execute("SELECT * FROM configs")]
        catalog = [dict(r) for r in db.execute("SELECT * FROM catalog WHERE custom=1 OR image IS NOT NULL")]
        z.writestr("export.json", json.dumps(dict(version=1, created=datetime.datetime.now().isoformat(timespec="seconds"),
                                                  profiles=profiles, configs=configs, catalog=catalog), ensure_ascii=False, indent=1))
        for f in pathlib.Path(media_dir).glob("*"):
            if f.is_file():
                z.write(f, f"media/{f.name}")
        if with_documents:
            pname = {p["id"]: p["name"] for p in profiles}
            for c in configs:
                try:
                    cfg = export.attach_images(db, json.loads(c["data"]))
                    base = f'dokumente/{_safe(pname.get(c["profile_id"], "profil"))}/{_safe(c["name"])}'
                    z.writestr(base + ".pdf", export.to_pdf(cfg, c["name"], pname.get(c["profile_id"], ""), media_dir))
                    z.writestr(base + ".csv", export.to_csv(cfg))
                except Exception as ex:  # ein defekter Eintrag darf die Sicherung nicht verhindern
                    z.writestr(f'dokumente/FEHLER-{c["id"]}.txt', str(ex))
    return buf.getvalue()


def _safe(s):
    return "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in str(s)).strip() or "unbenannt"


def run(db, media_dir, targets):
    data = build_zip(db, media_dir)
    fname = "verteiler-sicherung-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"
    results = []
    for t in targets:
        kind = t.get("type")
        try:
            if kind == "local":
                d = pathlib.Path(t["path"])
                d.mkdir(parents=True, exist_ok=True)
                (d / fname).write_bytes(data)
                results.append(dict(target=f"Ordner {d}", ok=True, detail=fname))
            elif kind == "webdav":
                url = t["url"].rstrip("/") + "/" + fname
                auth = (t.get("user", ""), t.get("password", "")) if t.get("user") else None
                r = httpx.put(url, content=data, auth=auth, timeout=120)
                r.raise_for_status()
                results.append(dict(target=f"WebDAV {t['url']}", ok=True, detail=fname))
            elif kind == "rclone":
                if not shutil.which("rclone"):
                    raise RuntimeError("rclone ist nicht installiert (apt install rclone, danach 'rclone config')")
                with tempfile.TemporaryDirectory() as td:
                    p = pathlib.Path(td) / fname
                    p.write_bytes(data)
                    cp = subprocess.run(["rclone", "copy", str(p), t["remote"]], capture_output=True, text=True, timeout=600)
                    if cp.returncode:
                        raise RuntimeError(cp.stderr.strip()[-400:] or "rclone-Fehler")
                results.append(dict(target=f"rclone {t['remote']}", ok=True, detail=fname))
            else:
                raise RuntimeError("unbekannter Zieltyp")
        except Exception as ex:
            results.append(dict(target=f"{kind} {t.get('path') or t.get('url') or t.get('remote') or ''}", ok=False, detail=str(ex)))
    return results, len(data)
