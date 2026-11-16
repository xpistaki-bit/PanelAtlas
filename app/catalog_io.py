"""Katalog-Import: CSV und BMEcat (ETIM). Katalog-Export als CSV."""
import csv
import io
import json
import re
import zipfile
from xml.etree import ElementTree as ET

TE = 17.5

# ---------------------------------------------------------------- CSV
CSV_COLS = ["kind", "manufacturer", "series", "article", "name", "category", "width_mm", "width_te", "height_mm", "poles", "current_a",
            "characteristic", "rcd_ma", "rcd_type", "color", "rows", "fields", "te_per_row", "row_pitch_mm", "depth_mm", "mount", "note", "image_url"]
ALIASES = {"art": "kind", "typ": "kind", "hersteller": "manufacturer", "serie": "series", "artikel": "article", "artikelnummer": "article",
           "bezeichnung": "name", "description": "name", "kategorie": "category", "geräteart": "category", "breite_mm": "width_mm", "breite mm": "width_mm",
           "breite_te": "width_te", "breite te": "width_te", "te": "width_te", "höhe_mm": "height_mm", "höhe mm": "height_mm", "pole": "poles",
           "nennstrom": "current_a", "nennstrom a": "current_a", "charakteristik": "characteristic", "fi_ma": "rcd_ma", "fi ma": "rcd_ma",
           "fi_typ": "rcd_type", "farbe": "color", "reihen": "rows", "felder": "fields", "te_je_reihe": "te_per_row", "te je reihe": "te_per_row",
           "reihenabstand_mm": "row_pitch_mm", "tiefe_mm": "depth_mm", "montage": "mount", "hinweis": "note", "bild_url": "image_url", "bild": "image_url"}
KINDS = {"device": "device", "gerät": "device", "geraet": "device", "enclosure": "enclosure", "schrank": "enclosure", "": "device"}
CATS = {"ls": "ls", "mcb": "ls", "rcd": "rcd", "fi": "rcd", "rccb": "rcd", "rcbo": "rcbo", "fi/ls": "rcbo", "afdd": "afdd", "spd": "spd", "switch": "switch",
        "schalter": "switch", "terminal": "terminal", "klemme": "terminal", "hlak": "hlak", "relay": "relay", "blank": "blank", "other": "other", "": "other"}
NUM = ("width_mm", "height_mm", "poles", "current_a", "rcd_ma", "rows", "fields", "te_per_row", "row_pitch_mm", "depth_mm")


def _f(v):
    if v is None:
        return None
    v = str(v).strip().replace(",", ".")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_csv(raw):
    """-> (einträge, fehlerliste). Trennzeichen ; oder , wird erkannt."""
    text = raw.decode("utf-8-sig", errors="replace")
    first = text.splitlines()[0] if text.strip() else ""
    delim = ";" if first.count(";") >= first.count(",") else ","
    rd = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in rd if any(c.strip() for c in r)]
    if not rows:
        return [], ["Datei ist leer"]
    head = [ALIASES.get(h.strip().lower(), h.strip().lower()) for h in rows[0]]
    if "article" not in head:
        return [], ["Spalte 'article' (Artikel) fehlt"]
    out, errs = [], []
    for n, r in enumerate(rows[1:], start=2):
        d = {h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head) if h in CSV_COLS}
        kind = KINDS.get(d.get("kind", "").lower())
        if not kind or not d.get("article"):
            errs.append(f"Zeile {n}: Art oder Artikel fehlt/unbekannt")
            continue
        for k in NUM:
            if k in d:
                d[k] = _f(d[k])
        w = d.get("width_mm") or ((_f(d.get("width_te")) or 0) * TE) or None
        e = dict(kind=kind, manufacturer=d.get("manufacturer", ""), series=d.get("series", ""), article=d["article"], name=d.get("name", ""))
        if kind == "device":
            if not w:
                errs.append(f"Zeile {n}: Breite fehlt (width_mm oder width_te)")
                continue
            e["data"] = dict(category=CATS.get((d.get("category") or "").lower(), "other"), width_mm=round(w, 2), height_mm=d.get("height_mm") or 85,
                             poles=int(d.get("poles") or 1), current_a=d.get("current_a"), characteristic=d.get("characteristic", ""),
                             rcd_ma=d.get("rcd_ma"), rcd_type=d.get("rcd_type", ""), color=d.get("color", ""), note=d.get("note", ""), verified=True, source="CSV")
        else:
            if not (w and d.get("height_mm") and d.get("rows")):
                errs.append(f"Zeile {n}: Schrank braucht width_mm, height_mm und rows")
                continue
            e["data"] = dict(width_mm=w, height_mm=d["height_mm"], depth_mm=d.get("depth_mm"), rows=int(d["rows"]), fields=int(d.get("fields") or 1),
                             te_per_row=int(d.get("te_per_row") or 12), row_pitch_mm=d.get("row_pitch_mm") or 125,
                             mount=(d.get("mount") or "AP").upper()[:2], note=d.get("note", ""), verified=True, source="CSV")
        if d.get("image_url"):
            e["data"]["image_url"] = d["image_url"]
        out.append(e)
    return out, errs


def export_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(CSV_COLS)
    for r in rows:
        d = json.loads(r["data"])
        vals = dict(kind=r["kind"], manufacturer=r["manufacturer"], series=r["series"], article=r["article"], name=r["name"], **d)
        if r["kind"] == "device" and d.get("width_mm"):
            vals["width_te"] = round(d["width_mm"] / TE, 2)
        w.writerow(["" if vals.get(c) is None else str(vals.get(c)).replace(".", ",") if isinstance(vals.get(c), float) else vals.get(c) for c in CSV_COLS])
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ---------------------------------------------------------------- BMEcat / ETIM
# ETIM-Klasse -> Geräteart. Geprüft: EC000042, EC000003, EC000214, EC000897. Die übrigen sind Vorschläge und
# lassen sich beim Import ergänzen/überschreiben ("EC000905=rcbo").
CLASS_MAP = {"EC000042": "ls", "EC000003": "rcd", "EC000905": "rcbo", "EC000941": "spd", "EC000897": "terminal", "EC000214": "enclosure"}
CLASS_VERIFIED = {"EC000042", "EC000003", "EC000897", "EC000214"}
EF = dict(te="EF002950", width=("EF000008", "EF008808"), height=("EF000040", "EF008809"), depth=("EF000049", "EF008810"), poles=("EF008618", "EF001391", "EF005548"),
          current="EF000227", char="EF000889", fault="EF002358", rows="EF000266")


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def open_bmecat(path):
    """Liefert ein Dateiobjekt auf die XML – auch aus einer ZIP-Datei."""
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        xmls = sorted((n for n in z.namelist() if n.lower().endswith(".xml")), key=lambda n: -z.getinfo(n).file_size)
        if not xmls:
            raise ValueError("ZIP enthält keine XML-Datei")
        return z.open(xmls[0])
    return open(path, "rb")


def _text(el, *names):
    for e in el.iter():
        if _local(e.tag) in names and e.text and e.text.strip():
            return e.text.strip()
    return ""


def _product(el, class_map):
    cls, feats = "", {}
    for grp in el.iter():
        if _local(grp.tag) not in ("PRODUCT_FEATURES", "ARTICLE_FEATURES"):
            continue
        gid = _text(grp, "REFERENCE_FEATURE_GROUP_ID")
        if not gid.upper().startswith("EC"):
            continue
        cls = gid.upper()
        for f in grp:
            if _local(f.tag) != "FEATURE":
                continue
            name, vals = "", []
            for c in f:
                t = _local(c.tag)
                if t == "FNAME":
                    name = (c.text or "").strip().upper()
                elif t == "FVALUE" and c.text:
                    vals.append(c.text.strip())
            if name:
                feats[name] = vals
    if cls not in class_map:
        return cls, None
    cat = class_map[cls]
    desc = _text(el, "DESCRIPTION_SHORT")
    article = _text(el, "MANUFACTURER_PID", "MANUFACTURER_AID") or _text(el, "SUPPLIER_PID", "SUPPLIER_AID")
    man = _text(el, "MANUFACTURER_NAME")
    series = _text(el, "MANUFACTURER_TYPE_DESCR")

    def num(key):
        keys = EF[key] if isinstance(EF[key], tuple) else (EF[key],)
        for k in keys:
            for v in feats.get(k, []):
                x = _f(v)
                if x is not None:
                    return x
        return None

    image = ""
    for m in el.iter():
        if _local(m.tag) == "MIME":
            src, typ = _text(m, "MIME_SOURCE"), _text(m, "MIME_TYPE").lower()
            if src.lower().startswith("http") and ("image" in typ or re.search(r"\.(jpe?g|png|webp)(\?|$)", src.lower())):
                image = src
                break
    note = f"BMEcat-Import, ETIM {cls}"
    if cat == "enclosure":
        w, h, rows, te = num("width"), num("height"), num("rows"), num("te")
        if not (w and h and rows and te):
            return cls, None
        fields = int(round(te / 12)) if te > 14 and te % 12 == 0 else 1
        low = desc.lower()
        mount = "UP" if re.search(r"unterputz|\bup\b|flush", low) else "HW" if "hohlwand" in low else "AP"
        data = dict(width_mm=w, height_mm=h, depth_mm=num("depth"), rows=int(rows), fields=fields, te_per_row=int(te / fields), row_pitch_mm=125,
                    mount=mount, verified=False, note=note + "; Reihenabstand und Montageart prüfen", source="BMEcat")
        kind = "enclosure"
    else:
        te, wmm = num("te"), num("width")
        w = te * TE if te else wmm
        if not w:
            return cls, None
        poles = num("poles")
        char = next((v for v in feats.get(EF["char"], []) if not v.upper().startswith("EV")), "")
        m = re.search(r"\b([BCDKZ])\s?(\d{1,3})(?:\s?A)?\b", desc)
        if not char and m:
            char = m.group(1)
        cur = num("current") or (float(m.group(2)) if m else None)
        fault = num("fault")
        rcd_ma = (fault * 1000 if fault and fault < 5 else fault) if cat in ("rcd", "rcbo") else None
        t = re.search(r"\bTyp(?:e)?\s?(AC|A|F|B\+?)\b", desc)
        color = ""
        if cat == "terminal":
            low = desc.lower()
            color = "pe" if re.search(r"\bpe\b|schutzleiter|grün-gelb|green-yellow", low) else "blue" if re.search(r"\bbu\b|blau|blue", low) else ""
        hmm = num("height")
        data = dict(category=cat, width_mm=round(w, 2), height_mm=hmm or (50 if cat == "terminal" else 85), poles=int(poles or 1), current_a=cur,
                    characteristic=char, rcd_ma=rcd_ma, rcd_type=t.group(1) if t else "", color=color, verified=bool(te or wmm) and cls in CLASS_VERIFIED,
                    note=note + ("" if hmm else "; Höhe ist ein Standardwert"), source="BMEcat")
        kind = "device"
    if image:
        data["image_url"] = image
    return cls, dict(kind=kind, manufacturer=man, series=series, article=article, name=desc, data=data)


def parse_bmecat(path, class_map=None, text_filter="", limit=5000, sample_only=False):
    """Liest eine BMEcat-Datei streamend. -> dict(total, matched, by_class, entries, truncated)"""
    class_map = class_map or CLASS_MAP
    needles = [w for w in text_filter.lower().split() if w]
    total = matched = 0
    by_class, entries, truncated = {}, [], False
    with open_bmecat(path) as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if _local(el.tag) not in ("PRODUCT", "ARTICLE"):
                continue
            total += 1
            cls, e = _product(el, class_map)
            el.clear()
            if cls:
                c = by_class.setdefault(cls, dict(total=0, usable=0, category=class_map.get(cls)))
                c["total"] += 1
            if not e or not e["article"]:
                continue
            if needles and not all(n in f'{e["manufacturer"]} {e["article"]} {e["name"]} {e["series"]}'.lower() for n in needles):
                continue
            by_class[cls]["usable"] += 1
            matched += 1
            if len(entries) < (20 if sample_only else limit):
                entries.append(e)
            elif not sample_only:
                truncated = True
    return dict(total=total, matched=matched, by_class=by_class, entries=entries, truncated=truncated)


def parse_class_map(text):
    """'EC000905=rcbo, EC001234=switch' -> dict; ergänzt die Vorgaben."""
    m = dict(CLASS_MAP)
    for part in re.split(r"[,\s;]+", text or ""):
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip().upper(), v.strip().lower()
            if re.fullmatch(r"EC\d{6}", k):
                if v in ("", "-", "skip"):
                    m.pop(k, None)
                elif v in set(CATS.values()) | {"enclosure"}:
                    m[k] = v
    return m
