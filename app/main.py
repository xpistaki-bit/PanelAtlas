"""PanelAtlas – Web-App (FastAPI + SQLite)."""
import contextlib
import datetime
import hashlib
import hmac
import io
import json
import os
import pathlib
import secrets
import sqlite3
import threading
import time
import uuid
import zipfile

import httpx
from fastapi import Body, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import backup, catalog_io, export
from .checks import run_checks, stats
from .render import render_svg

BASE = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get("VERTEILER_DATA", BASE.parent / "data"))
MEDIA = DATA / "media"
MEDIA.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "verteiler.db"
COOKIE = "vs_session"

app = FastAPI(title="PanelAtlas", docs_url=None, redoc_url=None)


@contextlib.contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY, name TEXT NOT NULL, pw_hash TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS configs(id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            name TEXT NOT NULL, data TEXT NOT NULL, updated TEXT);
        CREATE TABLE IF NOT EXISTS catalog(id INTEGER PRIMARY KEY, kind TEXT, manufacturer TEXT, series TEXT, article TEXT, name TEXT,
            data TEXT, image TEXT, custom INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS grants(token TEXT, profile_id INTEGER, created REAL);
        """)
        have = {(r["kind"], r["manufacturer"], r["article"]) for r in c.execute("SELECT kind, manufacturer, article FROM catalog")}
        for e in json.loads((BASE / "catalog_seed.json").read_text()):
            if (e["kind"], e["manufacturer"], e["article"]) not in have:
                c.execute("INSERT INTO catalog(kind, manufacturer, series, article, name, data, custom) VALUES(?,?,?,?,?,?,0)",
                          (e["kind"], e["manufacturer"], e["series"], e["article"], e["name"], json.dumps(e["data"], ensure_ascii=False)))


init()


# ------------------------------------------------------------------ Hilfen
def hash_pw(pw):
    salt = secrets.token_bytes(16)
    return salt.hex() + ":" + hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1).hex()


def check_pw(pw, stored):
    try:
        salt, h = stored.split(":")
        return hmac.compare_digest(hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex(), h)
    except Exception:
        return False


def get_setting(c, key, default=None):
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def set_setting(c, key, value):
    c.execute("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))


def granted(c, request, pid):
    tok = request.cookies.get(COOKIE)
    if not tok:
        return False
    return c.execute("SELECT 1 FROM grants WHERE token=? AND profile_id=?", (tok, pid)).fetchone() is not None


def grant(c, request, response, pid):
    tok = request.cookies.get(COOKIE) or secrets.token_urlsafe(32)
    c.execute("INSERT INTO grants(token, profile_id, created) VALUES(?,?,?)", (tok, pid, time.time()))
    response.set_cookie(COOKIE, tok, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)


def guard_profile(c, request, pid):
    p = c.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    if not p:
        raise HTTPException(404, "Profil nicht gefunden")
    if p["pw_hash"] and not granted(c, request, pid):
        raise HTTPException(401, "Anmeldung für dieses Profil erforderlich")
    return p


def guard_admin(c, request):
    if get_setting(c, "admin_pw") and not granted(c, request, 0):
        raise HTTPException(401, "Admin-Anmeldung erforderlich (unter Einstellungen anmelden)")


def lang_of(request):
    v = (request.query_params.get("lang") or request.headers.get("x-lang") or "de").lower()
    return "en" if v.startswith("en") else "de"


def load_config(c, request, cid):
    r = c.execute("SELECT * FROM configs WHERE id=?", (cid,)).fetchone()
    if not r:
        raise HTTPException(404, "Konfiguration nicht gefunden")
    p = guard_profile(c, request, r["profile_id"])
    return r, p


def config_payload(r, c, lang="de"):
    cfg = export.attach_images(c, json.loads(r["data"]))
    return dict(id=r["id"], name=r["name"], profile_id=r["profile_id"], updated=r["updated"], data=cfg,
                svg=render_svg(cfg, MEDIA, standalone=False), checks=run_checks(cfg, lang), stats=stats(cfg))


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def cat_row(r):
    d = json.loads(r["data"])
    return dict(id=r["id"], kind=r["kind"], manufacturer=r["manufacturer"], series=r["series"], article=r["article"], name=r["name"],
                image=r["image"], custom=bool(r["custom"]), **d)


def normalize(cfg):
    cfg.setdefault("items", [])
    cfg.setdefault("norm_checks", True)
    cfg.setdefault("ignored", [])
    cfg.setdefault("view", {})
    e = cfg.get("enclosure") or {}
    for k in ("width_mm", "height_mm", "rows"):
        if not e.get(k):
            raise HTTPException(400, "Schrank unvollständig: " + k)
    for it in cfg["items"]:
        it.setdefault("id", uuid.uuid4().hex[:10])
        if "dev" not in it:
            raise HTTPException(400, "Gerät ohne Katalogdaten")
    return cfg


# ------------------------------------------------------------------ Status / Anmeldung
@app.get("/api/state")
def state(request: Request):
    with db() as c:
        return dict(admin_locked=bool(get_setting(c, "admin_pw")), admin=granted(c, request, 0) or not get_setting(c, "admin_pw"))


@app.post("/api/admin/login")
def admin_login(request: Request, response: Response, body: dict = Body(...)):
    with db() as c:
        pw = get_setting(c, "admin_pw")
        if pw and not check_pw(body.get("password", ""), pw):
            raise HTTPException(403, "Falsches Passwort")
        grant(c, request, response, 0)
    return dict(ok=True)


@app.post("/api/admin/password")
def admin_password(request: Request, response: Response, body: dict = Body(...)):
    with db() as c:
        guard_admin(c, request)
        pw = body.get("password") or ""
        set_setting(c, "admin_pw", hash_pw(pw) if pw else None)
        if pw:
            grant(c, request, response, 0)
    return dict(ok=True)


@app.post("/api/logout")
def logout(request: Request, response: Response):
    tok = request.cookies.get(COOKIE)
    if tok:
        with db() as c:
            c.execute("DELETE FROM grants WHERE token=?", (tok,))
    response.delete_cookie(COOKIE)
    return dict(ok=True)


# ------------------------------------------------------------------ Profile
@app.get("/api/profiles")
def profiles(request: Request):
    with db() as c:
        out = []
        for p in c.execute("SELECT * FROM profiles ORDER BY name COLLATE NOCASE"):
            n = c.execute("SELECT COUNT(*) n FROM configs WHERE profile_id=?", (p["id"],)).fetchone()["n"]
            out.append(dict(id=p["id"], name=p["name"], locked=bool(p["pw_hash"]), open=not p["pw_hash"] or granted(c, request, p["id"]), configs=n))
        return out


@app.post("/api/profiles")
def profile_create(request: Request, response: Response, body: dict = Body(...)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Name fehlt")
    with db() as c:
        cur = c.execute("INSERT INTO profiles(name, pw_hash, created) VALUES(?,?,?)", (name, hash_pw(body["password"]) if body.get("password") else None, now()))
        if body.get("password"):
            grant(c, request, response, cur.lastrowid)
        return dict(id=cur.lastrowid)


@app.post("/api/profiles/{pid}/login")
def profile_login(pid: int, request: Request, response: Response, body: dict = Body(...)):
    with db() as c:
        p = c.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, "Profil nicht gefunden")
        if p["pw_hash"] and not check_pw(body.get("password", ""), p["pw_hash"]):
            raise HTTPException(403, "Falsches Passwort")
        grant(c, request, response, pid)
    return dict(ok=True)


@app.put("/api/profiles/{pid}")
def profile_update(pid: int, request: Request, response: Response, body: dict = Body(...)):
    with db() as c:
        guard_profile(c, request, pid)
        if body.get("name"):
            c.execute("UPDATE profiles SET name=? WHERE id=?", (body["name"].strip(), pid))
        if "password" in body:
            pw = body["password"] or ""
            c.execute("UPDATE profiles SET pw_hash=? WHERE id=?", (hash_pw(pw) if pw else None, pid))
            c.execute("DELETE FROM grants WHERE profile_id=?", (pid,))
            if pw:
                grant(c, request, response, pid)
    return dict(ok=True)


@app.delete("/api/profiles/{pid}")
def profile_delete(pid: int, request: Request):
    with db() as c:
        guard_profile(c, request, pid)
        c.execute("DELETE FROM profiles WHERE id=?", (pid,))
    return dict(ok=True)


# ------------------------------------------------------------------ Konfigurationen
@app.get("/api/profiles/{pid}/configs")
def configs(pid: int, request: Request):
    with db() as c:
        p = guard_profile(c, request, pid)
        out = []
        for r in c.execute("SELECT * FROM configs WHERE profile_id=? ORDER BY name COLLATE NOCASE", (pid,)):
            cfg = json.loads(r["data"])
            e = cfg["enclosure"]
            out.append(dict(id=r["id"], name=r["name"], updated=r["updated"], location=cfg.get("location", ""),
                            enclosure=f'{e.get("manufacturer","")} {e.get("article","")}'.strip(), items=len(cfg.get("items", [])), stats=stats(cfg)))
        return dict(profile=dict(id=p["id"], name=p["name"], locked=bool(p["pw_hash"])), configs=out)


@app.post("/api/profiles/{pid}/configs")
def config_create(pid: int, request: Request, body: dict = Body(...)):
    with db() as c:
        guard_profile(c, request, pid)
        if body.get("copy_of"):
            src, _ = load_config(c, request, int(body["copy_of"]))
            data, name = src["data"], body.get("name") or src["name"] + " (Kopie)"
        else:
            e = c.execute("SELECT * FROM catalog WHERE id=? AND kind='enclosure'", (body.get("enclosure_id"),)).fetchone()
            if e:
                enc = cat_row(e)
            elif body.get("enclosure"):
                enc = body["enclosure"]
            else:
                raise HTTPException(400, "Schrank fehlt")
            data = json.dumps(normalize(dict(enclosure=enc, items=[], location=body.get("location", ""))), ensure_ascii=False)
            name = (body.get("name") or "").strip() or "Neuer Verteiler"
        cur = c.execute("INSERT INTO configs(profile_id, name, data, updated) VALUES(?,?,?,?)", (pid, name, data, now()))
        return dict(id=cur.lastrowid)


@app.get("/api/configs/{cid}")
def config_get(cid: int, request: Request):
    with db() as c:
        r, p = load_config(c, request, cid)
        out = config_payload(r, c, lang_of(request))
        out["profile_name"] = p["name"]
        return out


@app.put("/api/configs/{cid}")
def config_put(cid: int, request: Request, body: dict = Body(...)):
    with db() as c:
        r, p = load_config(c, request, cid)
        name = (body.get("name") or r["name"]).strip()
        data = json.dumps(normalize(body["data"]), ensure_ascii=False) if "data" in body else r["data"]
        c.execute("UPDATE configs SET name=?, data=?, updated=? WHERE id=?", (name, data, now(), cid))
        set_setting(c, "last_change", time.time())
        out = config_payload(c.execute("SELECT * FROM configs WHERE id=?", (cid,)).fetchone(), c, lang_of(request))
        out["profile_name"] = p["name"]
        return out


@app.delete("/api/configs/{cid}")
def config_delete(cid: int, request: Request):
    with db() as c:
        load_config(c, request, cid)
        c.execute("DELETE FROM configs WHERE id=?", (cid,))
    return dict(ok=True)


def _fname(name, ext):
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name) or "verteiler"
    return f'{safe}.{ext}'


@app.get("/api/configs/{cid}/pdf")
def config_pdf(cid: int, request: Request, download: int = 0):
    with db() as c:
        r, p = load_config(c, request, cid)
        cfg = export.attach_images(c, json.loads(r["data"]))
    pdf = export.to_pdf(cfg, r["name"], p["name"], MEDIA, lang_of(request))
    disp = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'{disp}; filename="{_fname(r["name"], "pdf")}"'})


@app.get("/api/configs/{cid}/csv")
def config_csv(cid: int, request: Request, light: int = 0):
    with db() as c:
        r, _ = load_config(c, request, cid)
    fn = _fname(r["name"] + ("-light" if light else ""), "csv")
    return Response(export.to_csv(json.loads(r["data"]), lang_of(request), bool(light)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@app.get("/api/configs/{cid}/labels")
def config_labels(cid: int, request: Request):
    """Etiketten: ?format=pdf liefert das PDF (1:1), sonst die Seiten als SVG zur Vorschau."""
    with db() as c:
        r, _ = load_config(c, request, cid)
    cfg = json.loads(r["data"])
    opts = dict(cfg.get("labels") or {})
    opts.update({k: v for k, v in request.query_params.items() if k in export.LABEL_DEFAULTS})
    if request.query_params.get("format") == "pdf":
        return Response(export.labels_pdf(cfg, r["name"], opts, lang_of(request)), media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{_fname(r["name"] + "-etiketten", "pdf")}"'})
    return dict(pages=export.label_pages(cfg, r["name"], opts, lang_of(request)), options=export.label_opts(opts))


@app.get("/api/configs/{cid}/svg")
def config_svg(cid: int, request: Request):
    with db() as c:
        r, _ = load_config(c, request, cid)
        cfg = export.attach_images(c, json.loads(r["data"]))
    return Response(render_svg(cfg, MEDIA, embed=True), media_type="image/svg+xml")


@app.get("/api/configs/{cid}/json")
def config_json(cid: int, request: Request):
    with db() as c:
        r, _ = load_config(c, request, cid)
    return Response(json.dumps(dict(name=r["name"], data=json.loads(r["data"])), ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(r["name"], "json")}"'})


# ------------------------------------------------------------------ Katalog
@app.get("/api/catalog")
def catalog(kind: str = ""):
    with db() as c:
        q = "SELECT * FROM catalog" + (" WHERE kind=?" if kind else "") + " ORDER BY manufacturer COLLATE NOCASE, series, id"
        return [cat_row(r) for r in c.execute(q, (kind,) if kind else ())]


CAT_FIELDS = ("kind", "manufacturer", "series", "article", "name")


@app.post("/api/catalog")
def catalog_create(request: Request, body: dict = Body(...)):
    with db() as c:
        guard_admin(c, request)
        if body.get("kind") not in ("enclosure", "device") or not body.get("article"):
            raise HTTPException(400, "Art und Artikelnummer sind erforderlich")
        data = {k: v for k, v in body.items() if k not in CAT_FIELDS + ("id", "image", "custom")}
        cur = c.execute("INSERT INTO catalog(kind, manufacturer, series, article, name, data, custom) VALUES(?,?,?,?,?,?,1)",
                        (body["kind"], body.get("manufacturer", ""), body.get("series", ""), body["article"], body.get("name", ""), json.dumps(data, ensure_ascii=False)))
        return cat_row(c.execute("SELECT * FROM catalog WHERE id=?", (cur.lastrowid,)).fetchone())


@app.put("/api/catalog/{iid}")
def catalog_update(iid: int, request: Request, body: dict = Body(...)):
    with db() as c:
        guard_admin(c, request)
        r = c.execute("SELECT * FROM catalog WHERE id=?", (iid,)).fetchone()
        if not r:
            raise HTTPException(404, "Eintrag nicht gefunden")
        data = json.loads(r["data"])
        data.update({k: v for k, v in body.items() if k not in CAT_FIELDS + ("id", "image", "custom")})
        c.execute("UPDATE catalog SET manufacturer=?, series=?, article=?, name=?, data=? WHERE id=?",
                  (body.get("manufacturer", r["manufacturer"]), body.get("series", r["series"]), body.get("article", r["article"]),
                   body.get("name", r["name"]), json.dumps(data, ensure_ascii=False), iid))
        return cat_row(c.execute("SELECT * FROM catalog WHERE id=?", (iid,)).fetchone())


@app.delete("/api/catalog/{iid}")
def catalog_delete(iid: int, request: Request):
    with db() as c:
        guard_admin(c, request)
        c.execute("DELETE FROM catalog WHERE id=?", (iid,))
    return dict(ok=True)


def _upsert(c, entries):
    have = {(r["kind"], r["manufacturer"], r["article"]): r["id"] for r in c.execute("SELECT id, kind, manufacturer, article FROM catalog")}
    new = upd = 0
    for e in entries:
        key = (e["kind"], e["manufacturer"], e["article"])
        data = json.dumps(e["data"], ensure_ascii=False)
        if key in have:
            c.execute("UPDATE catalog SET series=?, name=?, data=? WHERE id=?", (e["series"], e["name"], data, have[key]))
            upd += 1
        else:
            cur = c.execute("INSERT INTO catalog(kind, manufacturer, series, article, name, data, custom) VALUES(?,?,?,?,?,?,1)",
                            (e["kind"], e["manufacturer"], e["series"], e["article"], e["name"], data))
            have[key] = cur.lastrowid
            new += 1
    return new, upd


@app.get("/api/catalog/export.csv")
def catalog_export(kind: str = "", template: int = 0):
    with db() as c:
        rows = [] if template else c.execute("SELECT * FROM catalog" + (" WHERE kind=?" if kind else "") + " ORDER BY kind, manufacturer, id", (kind,) if kind else ()).fetchall()
        if template:
            rows = c.execute("SELECT * FROM catalog WHERE article IN ('MBN116','CDA440D','3209510','VA48CN') ORDER BY kind, id").fetchall()
    fn = "katalog-vorlage.csv" if template else "katalog.csv"
    return Response(catalog_io.export_csv(rows), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@app.post("/api/catalog/import/csv")
async def catalog_import_csv(request: Request, file: UploadFile = File(...)):
    with db() as c:
        guard_admin(c, request)
    entries, errs = catalog_io.parse_csv(await file.read())
    with db() as c:
        new, upd = _upsert(c, entries)
    return dict(new=new, updated=upd, errors=errs[:50])


TMP = DATA / "tmp"


@app.post("/api/catalog/import/bmecat")
async def catalog_import_bmecat(request: Request, file: UploadFile = File(...)):
    """Schritt 1: Datei hochladen und analysieren (Vorschau)."""
    with db() as c:
        guard_admin(c, request)
    TMP.mkdir(exist_ok=True)
    for old in TMP.glob("*.upload"):
        if time.time() - old.stat().st_mtime > 6 * 3600:
            old.unlink(missing_ok=True)
    token = secrets.token_hex(8)
    path = TMP / f"{token}.upload"
    with open(path, "wb") as out:
        while chunk := await file.read(1 << 20):
            out.write(chunk)
    try:
        res = catalog_io.parse_bmecat(path, sample_only=True)
    except Exception as ex:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"Datei ist kein lesbares BMEcat: {ex}")
    return dict(token=token, defaults=catalog_io.CLASS_MAP, verified=sorted(catalog_io.CLASS_VERIFIED), **res)


@app.post("/api/catalog/import/bmecat/{token}")
def catalog_import_bmecat_run(token: str, request: Request, body: dict = Body(...)):
    """Schritt 2: mit Filter und Klassenzuordnung importieren (dry=true nur zählen)."""
    with db() as c:
        guard_admin(c, request)
    path = TMP / f"{''.join(ch for ch in token if ch.isalnum())}.upload"
    if not path.exists():
        raise HTTPException(404, "Hochgeladene Datei nicht mehr vorhanden, bitte erneut hochladen")
    cmap = catalog_io.parse_class_map(body.get("classes", ""))
    only = [k for k in (body.get("only") or []) if k in cmap]
    if only:
        cmap = {k: cmap[k] for k in only}
    res = catalog_io.parse_bmecat(path, cmap, body.get("filter", ""), limit=int(body.get("limit") or 5000), sample_only=bool(body.get("dry")))
    if body.get("dry"):
        return res
    with db() as c:
        new, upd = _upsert(c, res["entries"])
    path.unlink(missing_ok=True)
    return dict(new=new, updated=upd, matched=res["matched"], truncated=res["truncated"])


def _store_image(iid, raw):
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        raise HTTPException(400, "Datei ist kein lesbares Bild (PNG, JPEG, WebP, GIF)")
    im = im.convert("RGBA")
    im.thumbnail((900, 900))
    name = f"cat{iid}-{secrets.token_hex(4)}.png"
    im.save(MEDIA / name, "PNG")
    with db() as c:
        old = c.execute("SELECT image FROM catalog WHERE id=?", (iid,)).fetchone()
        if not old:
            raise HTTPException(404, "Eintrag nicht gefunden")
        c.execute("UPDATE catalog SET image=? WHERE id=?", (name, iid))
        return cat_row(c.execute("SELECT * FROM catalog WHERE id=?", (iid,)).fetchone())


@app.post("/api/catalog/{iid}/image")
async def catalog_image(iid: int, request: Request, file: UploadFile = File(...)):
    with db() as c:
        guard_admin(c, request)
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(400, "Bild ist größer als 8 MB")
    return _store_image(iid, raw)


@app.post("/api/catalog/{iid}/image-url")
def catalog_image_url(iid: int, request: Request, body: dict = Body(...)):
    with db() as c:
        guard_admin(c, request)
    url = (body.get("url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Bitte eine http(s)-Adresse angeben")
    try:
        r = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0 (PanelAtlas)"})
        r.raise_for_status()
    except Exception as ex:
        raise HTTPException(400, f"Bild konnte nicht geladen werden: {ex}")
    if len(r.content) > 8 * 1024 * 1024:
        raise HTTPException(400, "Bild ist größer als 8 MB")
    return _store_image(iid, r.content)


@app.delete("/api/catalog/{iid}/image")
def catalog_image_delete(iid: int, request: Request):
    with db() as c:
        guard_admin(c, request)
        c.execute("UPDATE catalog SET image=NULL WHERE id=?", (iid,))
    return dict(ok=True)


# ------------------------------------------------------------------ Sicherung
def _backup_settings(c):
    return get_setting(c, "backup", dict(targets=[], auto_hours=0))


@app.get("/api/backup")
def backup_get(request: Request):
    with db() as c:
        guard_admin(c, request)
        s = _backup_settings(c)
        for t in s["targets"]:
            if t.get("password"):
                t["password"] = "••••••"
        return dict(settings=s, last=get_setting(c, "backup_last"))


@app.put("/api/backup")
def backup_put(request: Request, body: dict = Body(...)):
    with db() as c:
        guard_admin(c, request)
        old = _backup_settings(c)["targets"]
        targets = body.get("targets", [])
        for i, t in enumerate(targets):
            if t.get("password") == "••••••" and i < len(old):
                t["password"] = old[i].get("password", "")
        set_setting(c, "backup", dict(targets=targets, auto_hours=int(body.get("auto_hours") or 0)))
    return dict(ok=True)


def _run_backup():
    with db() as c:
        targets = _backup_settings(c)["targets"]
        results, size = backup.run(c, MEDIA, targets)
        last = dict(time=now(), ts=time.time(), results=results, size=size)
        set_setting(c, "backup_last", last)
    return last


@app.post("/api/backup/run")
def backup_run(request: Request):
    with db() as c:
        guard_admin(c, request)
        if not _backup_settings(c)["targets"]:
            raise HTTPException(400, "Kein Sicherungsziel eingerichtet")
    return _run_backup()


@app.get("/api/backup/download")
def backup_download(request: Request):
    with db() as c:
        guard_admin(c, request)
        for p in c.execute("SELECT id FROM profiles WHERE pw_hash IS NOT NULL").fetchall():
            if not granted(c, request, p["id"]) and not (get_setting(c, "admin_pw") and granted(c, request, 0)):
                raise HTTPException(401, "Gesamtsicherung nur möglich, wenn alle geschützten Profile entsperrt sind oder ein Admin angemeldet ist")
        data = backup.build_zip(c, MEDIA)
    fn = "verteiler-sicherung-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@app.post("/api/backup/import")
async def backup_import(request: Request, file: UploadFile = File(...)):
    with db() as c:
        guard_admin(c, request)
    raw = await file.read()
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        exp = json.loads(z.read("export.json"))
    except Exception:
        raise HTTPException(400, "Keine gültige Sicherungsdatei")
    n_p = n_c = 0
    with db() as c:
        for n in z.namelist():
            if n.startswith("media/") and not n.endswith("/"):
                (MEDIA / pathlib.Path(n).name).write_bytes(z.read(n))
        have = {(r["kind"], r["manufacturer"], r["article"]): r["id"] for r in c.execute("SELECT id, kind, manufacturer, article FROM catalog")}
        for e in exp.get("catalog", []):
            key = (e["kind"], e["manufacturer"], e["article"])
            if key in have:
                if e.get("image"):
                    c.execute("UPDATE catalog SET image=? WHERE id=?", (e["image"], have[key]))
            else:
                c.execute("INSERT INTO catalog(kind, manufacturer, series, article, name, data, image, custom) VALUES(?,?,?,?,?,?,?,1)",
                          (e["kind"], e["manufacturer"], e["series"], e["article"], e["name"], e["data"], e.get("image")))
        names = {r["name"] for r in c.execute("SELECT name FROM profiles")}
        idmap = {}
        for p in exp.get("profiles", []):
            name = p["name"] if p["name"] not in names else p["name"] + " (importiert)"
            cur = c.execute("INSERT INTO profiles(name, pw_hash, created) VALUES(?,?,?)", (name, p.get("pw_hash"), p.get("created") or now()))
            idmap[p["id"]] = cur.lastrowid
            n_p += 1
        for cf in exp.get("configs", []):
            if cf["profile_id"] in idmap:
                c.execute("INSERT INTO configs(profile_id, name, data, updated) VALUES(?,?,?,?)", (idmap[cf["profile_id"]], cf["name"], cf["data"], cf.get("updated") or now()))
                n_c += 1
    return dict(profiles=n_p, configs=n_c)


def _auto_backup_loop():
    while True:
        time.sleep(600)
        try:
            with db() as c:
                s = _backup_settings(c)
                last = get_setting(c, "backup_last") or {}
                changed = get_setting(c, "last_change", 0)
            if s.get("auto_hours") and s["targets"] and changed > last.get("ts", 0) and time.time() - last.get("ts", 0) > s["auto_hours"] * 3600:
                _run_backup()
        except Exception as ex:  # Hintergrundsicherung darf den Dienst nicht beenden
            print("auto-backup:", ex)


threading.Thread(target=_auto_backup_loop, daemon=True).start()


ERR_EN = {
    "Profil nicht gefunden": "Profile not found", "Anmeldung für dieses Profil erforderlich": "Sign-in required for this profile",
    "Admin-Anmeldung erforderlich (unter Einstellungen anmelden)": "Admin sign-in required (sign in under Settings)",
    "Konfiguration nicht gefunden": "Configuration not found", "Falsches Passwort": "Wrong password", "Name fehlt": "Name missing",
    "Schrank fehlt": "Enclosure missing", "Eintrag nicht gefunden": "Entry not found", "Kein Sicherungsziel eingerichtet": "No backup target configured",
    "Keine gültige Sicherungsdatei": "Not a valid backup file", "Bild ist größer als 8 MB": "Image is larger than 8 MB",
    "Bitte eine http(s)-Adresse angeben": "Please enter an http(s) address", "Art und Artikelnummer sind erforderlich": "Kind and article number are required",
    "Datei ist kein lesbares Bild (PNG, JPEG, WebP, GIF)": "File is not a readable image (PNG, JPEG, WebP, GIF)",
    "Hochgeladene Datei nicht mehr vorhanden, bitte erneut hochladen": "Uploaded file no longer available, please upload again",
}


@app.exception_handler(HTTPException)
async def http_err(request, exc):
    detail = exc.detail
    if lang_of(request) == "en" and isinstance(detail, str):
        detail = ERR_EN.get(detail, detail)
    return JSONResponse({"error": detail}, status_code=exc.status_code)


app.mount("/media", StaticFiles(directory=MEDIA), name="media")


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=BASE / "static"), name="static")
