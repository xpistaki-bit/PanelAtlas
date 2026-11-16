"""PDF-, CSV- und Etiketten-Export (DE/EN)."""
import csv
import datetime
import io
import textwrap

import cairosvg
from pypdf import PdfReader, PdfWriter

from .checks import run_checks, stats
from .render import CAT_LABEL, PHASE_COLOR, TE, esc, layout, render_svg

FONT = 'font-family="DejaVu Sans, Arial, Helvetica, sans-serif"'
CAT_LABEL_EN = {"ls": "MCB", "rcd": "RCD", "rcbo": "RCBO", "afdd": "AFDD", "spd": "Surge protection", "switch": "Switch",
                "terminal": "Terminal block", "hlak": "Main branch terminal", "relay": "Switching device", "meter": "Meter", "blank": "Blank", "other": "Other"}
S = {
    "csv_head": (["Reihe", "Position", "Kennzeichnung", "Funktion", "Raum", "Hersteller", "Artikel", "Bezeichnung", "Kategorie", "Pole",
                  "Nennstrom A", "Charakteristik", "FI mA", "Außenleiter", "Zugeordneter FI", "Breite mm", "Breite TE", "Notiz"],
                 ["Row", "Position", "Designation", "Function", "Room", "Manufacturer", "Article", "Description", "Category", "Poles",
                  "Rated current A", "Characteristic", "RCD mA", "Phase", "Assigned RCD", "Width mm", "Width modules", "Note"]),
    "csv_light": (["Reihe", "Position", "Funktion", "Raum"], ["Row", "Position", "Function", "Room"]),
    "created": ("Erstellt am {d} · Dokumentation ersetzt keine Prüfung durch eine Elektrofachkraft",
                "Created on {d} · Documentation does not replace inspection by a qualified electrician"),
    "page": ("Seite", "Page"),
    "sub": ("{u:g} von {t:g} TE belegt · Maßstab ca. 1:{s:.1f}", "{u:g} of {t:g} modules used · scale approx. 1:{s:.1f}"),
    "cols": (["R/Pos", "Kennz.", "Funktion", "Raum", "Gerät", "L", "FI"], ["R/Pos", "Desig.", "Function", "Room", "Device", "L", "RCD"]),
    "hints": ("Hinweise aus Maß- und Normprüfung", "Notes from dimension and standards check"),
    "deviated": ("bewusst abgewichen", "deliberate deviation"),
    "error": ("Fehler", "Error"), "warn": ("Warnung", "Warning"), "info": ("Hinweis", "Note"),
    "notes": ("Notizen", "Notes"),
    "detail": ("Detail Reihe {a}–{b}", "Detail rows {a}–{b}"), "field": (" (Feld {f})", " (section {f})"),
    "scale": (" · Maßstab ca. 1:{s:.1f}", " · scale approx. 1:{s:.1f}"),
    "list": ("Stromkreis- und Geräteliste", "Circuit and device list"),
    "lbl_title": ("Beschriftungsstreifen", "Label strips"),
    "lbl_hint": ("Mit 100 % (tatsächliche Größe) drucken, nicht „an Seite anpassen“. Kontrollmaß: der Balken ist genau 100 mm lang.",
                 "Print at 100 % (actual size), not “fit to page”. Check: the bar is exactly 100 mm long."),
    "row": ("Reihe", "Row"),
}


def tr(key, lang):
    return S[key][1 if lang == "en" else 0]


def attach_images(con, cfg):
    """Übernimmt das aktuelle Katalogbild (Hersteller + Artikel) in die eingesetzten Geräte."""
    imgs = {(r["manufacturer"], r["article"]): r["image"] for r in con.execute("SELECT manufacturer, article, image FROM catalog WHERE kind='device'")}
    for it in cfg.get("items", []):
        key = (it["dev"].get("manufacturer"), it["dev"].get("article"))
        if key in imgs:
            it["dev"]["image"] = imgs[key]
    return cfg


def rows_table(cfg, lang="de"):
    g = layout(cfg)
    by_id = {i["id"]: i for i in cfg.get("items", [])}
    labels = CAT_LABEL_EN if lang == "en" else CAT_LABEL
    out = []
    for r in g["rows"]:
        for o in r["items"]:
            it, d = o["item"], o["item"]["dev"]
            rcd = by_id.get(it.get("rcd_id") or "")
            out.append(dict(
                reihe=r["idx"] + 1, pos=o["pos"], tag=it.get("tag", ""), function=it.get("function", ""), room=it.get("room", ""),
                manufacturer=d.get("manufacturer", ""), article=d.get("article", ""), name=d.get("name", ""),
                category=labels.get(d.get("category"), d.get("category", "")), poles=d.get("poles") or "",
                current=d.get("current_a") or "", char=d.get("characteristic") or "", rcd_ma=d.get("rcd_ma") or "",
                phase=it.get("phase", ""), rcd=(rcd.get("tag") or rcd["dev"].get("article", "")) if rcd else "",
                width_mm=o["w"], width_te=round(o["w"] / TE, 2), note=it.get("note", ""), cat=d.get("category")))
    return out


def _num(v, lang):
    return str(v) if lang == "en" else str(v).replace(".", ",")


def to_csv(cfg, lang="de", light=False):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    if light:
        w.writerow(tr("csv_light", lang))
        for r in rows_table(cfg, lang):
            if r["cat"] != "blank":
                w.writerow([r["reihe"], r["pos"], r["function"], r["room"]])
    else:
        w.writerow(tr("csv_head", lang))
        for r in rows_table(cfg, lang):
            w.writerow([r["reihe"], r["pos"], r["tag"], r["function"], r["room"], r["manufacturer"], r["article"], r["name"], r["category"],
                        r["poles"], r["current"], r["char"], r["rcd_ma"], r["phase"], r["rcd"],
                        _num(r["width_mm"], lang), _num(r["width_te"], lang), r["note"]])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _page(pw, ph, body, title, sub, page, pages, lang):
    today = datetime.date.today().strftime("%Y-%m-%d" if lang == "en" else "%d.%m.%Y")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{pw}mm" height="{ph}mm" viewBox="0 0 {pw} {ph}" {FONT}>'
            f'<rect width="{pw}" height="{ph}" fill="#fff"/>'
            f'<text x="12" y="14" font-size="5.2" font-weight="700" fill="#111">{esc(title)}</text>'
            f'<text x="12" y="20" font-size="3" fill="#444">{esc(sub)}</text>'
            f'<line x1="12" y1="23" x2="{pw-12}" y2="23" stroke="#111" stroke-width="0.4"/>'
            f'{body}'
            f'<text x="12" y="{ph-7}" font-size="2.6" fill="#666">{esc(tr("created", lang).format(d=today))}</text>'
            f'<text x="{pw-12}" y="{ph-7}" font-size="2.6" fill="#666" text-anchor="end">{tr("page", lang)} {page} / {pages}</text></svg>')


def _merge(svgs, title):
    w = PdfWriter()
    for s in svgs:
        pdf = cairosvg.svg2pdf(bytestring=s.encode("utf-8"))
        for p in PdfReader(io.BytesIO(pdf)).pages:
            w.add_page(p)
    w.add_metadata({"/Title": title})
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def to_pdf(cfg, name, profile_name, media_dir, lang="de"):
    e = cfg["enclosure"]
    W, H = float(e["width_mm"]) + 24, float(e["height_mm"]) + 24
    landscape = W > H
    pw, ph = (297, 210) if landscape else (210, 297)
    aw, ah = pw - 24, ph - 27 - 14
    scale = min(aw / W, ah / H, 1.0)
    dw, dh = W * scale, H * scale
    inner = render_svg(cfg, media_dir, embed=True, standalone=False)
    inner = inner.replace("<svg ", f'<svg x="{12+(aw-dw)/2:.2f}" y="27" width="{dw:.2f}" height="{dh:.2f}" ', 1)
    st = stats(cfg)
    sub = (f'{e.get("manufacturer","")} {e.get("article","")} · {e.get("name","")} · {e["width_mm"]:g} × {e["height_mm"]:g} mm · '
           + tr("sub", lang).format(u=st["used_te"], t=st["total_te"], s=1 / scale))
    title = f"{name} — {profile_name}" if profile_name else name
    if cfg.get("location"):
        title += f" · {cfg['location']}"

    heads = tr("cols", lang)
    cols = [(heads[0], 12, 12), (heads[1], 26, 14), (heads[2], 42, 38), (heads[3], 82, 30), (heads[4], 114, 50), (heads[5], 166, 10), (heads[6], 178, 20)]
    if landscape:
        k = 273 / 186
        cols = [(n, 12 + (x - 12) * k, w * k) for n, x, w in cols]
    lines = []
    for r in rows_table(cfg, lang):
        if r["cat"] == "blank":
            continue
        dev = f'{r["manufacturer"]} {r["article"]} · {r["name"]}'.strip()
        lines.append(("row", [f'{r["reihe"]}.{r["pos"]}', r["tag"], r["function"], r["room"], dev, r["phase"], r["rcd"]]))
    checks = run_checks(cfg, lang)
    wrap = 118 if not landscape else 170
    if checks:
        lines.append(("head", tr("hints", lang)))
        for c in checks:
            mark = tr("deviated", lang) if c["ignored"] else tr(c["level"], lang)
            txt = f'[{mark}] {c["text"]}' + (f' ({c["norm"]})' if c["norm"] else "")
            for j, ln in enumerate(textwrap.wrap(txt, wrap)):
                lines.append(("text", ("" if j else "• ") + ln))
    if cfg.get("notes"):
        lines.append(("head", tr("notes", lang)))
        for para in str(cfg["notes"]).splitlines():
            for ln in textwrap.wrap(para, wrap) or [""]:
                lines.append(("text", ln))
    per = int((ph - 27 - 8 - 16) / 5.6)
    chunks = [lines[i:i + per] for i in range(0, len(lines), per)] or []
    # Detailseiten: belegte Reihen vergrößert (je Feld, 3 Reihen pro Seite, Hochformat)
    g = layout(cfg)
    details = []
    for f in range(g["fields"]):
        frows = [r for r in g["rows"] if r["field"] == f]
        i = 0
        while i < len(frows):
            end = min(len(frows), i + 3)
            if end < len(frows) and frows[end]["blocked_by"] is not None:  # Zähler nicht zerschneiden
                owner = frows[end]["blocked_by"] - frows[0]["idx"]
                if owner > i:
                    end = owner  # Seite vor dem Zähler beenden
                else:
                    while end < len(frows) and frows[end]["blocked_by"] is not None:
                        end += 1
            part, i = frows[i:end], end
            if not any(r["items"] for r in part):
                continue
            crop = (f * g["field_w"], part[0]["cy"] - 47, g["field_w"], g["pitch"] * len(part) + 3)
            sc = min(186 / crop[2], 256 / crop[3], 1.0)
            d = render_svg(cfg, media_dir, embed=True, standalone=False, crop=crop)
            d = d.replace("<svg ", f'<svg x="{12+(186-crop[2]*sc)/2:.2f}" y="27" width="{crop[2]*sc:.2f}" height="{crop[3]*sc:.2f}" ', 1)
            lab = (tr("detail", lang).format(a=part[0]["idx"] + 1, b=part[-1]["idx"] + 1)
                   + (tr("field", lang).format(f=f + 1) if g["fields"] > 1 else "") + tr("scale", lang).format(s=1 / sc))
            details.append((d, lab))
    pages = 1 + len(details) + len(chunks)
    svgs = [_page(pw, ph, inner, title, sub, 1, pages, lang)]
    for n, (d, lab) in enumerate(details):
        svgs.append(_page(210, 297, d, title, lab, n + 2, pages, lang))
    for n, chunk in enumerate(chunks):
        b = [f'<rect x="12" y="27" width="{pw-24}" height="7" fill="#1f2a37"/>']
        for cn, cx, cw in cols:
            b.append(f'<text x="{cx+1.5:.2f}" y="31.8" font-size="3" font-weight="700" fill="#fff">{cn}</text>')
        y = 34
        for i, (kind, val) in enumerate(chunk):
            y += 5.6
            if kind == "row":
                if i % 2 == 0:
                    b.append(f'<rect x="12" y="{y-4:.2f}" width="{pw-24}" height="5.6" fill="#f3f4f6"/>')
                for ci, ((cn, cx, cw), v) in enumerate(zip(cols, val)):
                    v = str(v or "")
                    mx = max(2, int(cw / 1.75))
                    v = v if len(v) <= mx else v[:mx - 1] + "…"
                    wt = "700" if ci == 1 else "400"
                    b.append(f'<text x="{cx+1.5:.2f}" y="{y:.2f}" font-size="3" fill="#111" font-weight="{wt}">{esc(v)}</text>')
            elif kind == "head":
                b.append(f'<text x="12" y="{y:.2f}" font-size="3.6" font-weight="700" fill="#111">{esc(val)}</text>')
            else:
                b.append(f'<text x="13" y="{y:.2f}" font-size="2.8" fill="#222">{esc(val)}</text>')
        svgs.append(_page(pw, ph, "".join(b), title, tr("list", lang), n + 2 + len(details), pages, lang))
    return _merge(svgs, title)


# ------------------------------------------------------------------ Etiketten (Beschriftungsstreifen, Maßstab 1:1)
LABEL_DEFAULTS = dict(height=25.0, module=17.5, font=3.0, tag=True, function=True, room=True, rating=False, phase=True,
                      frame="solid", orient="auto", bold_tag=True, upper=False, terminals=False, gap=6.0)


def label_opts(raw):
    o = dict(LABEL_DEFAULTS)
    for k, v in (raw or {}).items():
        if k not in o:
            continue
        d = LABEL_DEFAULTS[k]
        try:
            if isinstance(d, bool):
                o[k] = v in (True, 1, "1", "true", "on", "True")
            elif isinstance(d, float):
                o[k] = float(v)
            else:
                o[k] = str(v)
        except (TypeError, ValueError):
            pass
    o["height"] = min(max(o["height"], 6), 80)
    o["module"] = min(max(o["module"], 15), 20)
    o["font"] = min(max(o["font"], 1.5), 8)
    return o


def _wrap_w(text, width, size):
    n = max(2, int(width / (size * 0.56)))
    return textwrap.wrap(text, n, break_long_words=True) or [""]


def _label_cell(it, x, y, w, h, o):
    d = it["dev"]
    cat = d.get("category")
    if cat == "blank" or (cat in ("terminal", "hlak") and not o["terminals"]):
        return ""
    s = []
    frame = {"solid": 'stroke="#000" stroke-width="0.2"', "dashed": 'stroke="#000" stroke-width="0.2" stroke-dasharray="1.2 0.8"',
             "thick": 'stroke="#000" stroke-width="0.6"', "none": 'stroke="none"'}.get(o["frame"], 'stroke="#000" stroke-width="0.2"')
    s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#fff" {frame}/>')
    top = 0.0
    if o["phase"] and it.get("phase") in PHASE_COLOR:
        s.append(f'<rect x="{x+0.3:.2f}" y="{y+0.3:.2f}" width="{w-0.6:.2f}" height="1.6" fill="{PHASE_COLOR[it["phase"]]}"/>')
        top = 2.0
    up = (lambda t: t.upper()) if o["upper"] else (lambda t: t)
    parts = []
    if o["tag"] and it.get("tag"):
        parts.append((up(it["tag"]), "700" if o["bold_tag"] else "400"))
    if o["rating"] and d.get("current_a"):
        parts.append((f'{d.get("characteristic") or ""}{d["current_a"]:g}' + ("" if d.get("characteristic") else " A"), "400"))
    if o["function"] and it.get("function"):
        parts.append((up(it["function"]), "400"))
    if o["room"] and it.get("room"):
        parts.append((up(it["room"]), "400"))
    if not parts:
        return "".join(s)
    size = o["font"]
    vertical = o["orient"] == "vertical" or (o["orient"] == "auto" and w < 30)
    # lange Wörter nicht mitten im Wort umbrechen: Schrift für diese Zelle bis auf 60 % verkleinern
    room_len = (h - top - 2) if vertical else (w - 2)
    longest = max(len(wd) for txt, _ in parts for wd in (txt.split() or [""]))
    if longest * size * 0.62 > room_len:
        size = max(size * 0.6, room_len / (longest * 0.62))
    lh = size * 1.25
    if vertical:
        avail_len, avail_across = h - top - 2, w - 1.5
        lines = []
        for txt, wt in parts:
            for ln in _wrap_w(txt, avail_len, size):
                lines.append((ln, wt))
        mx = max(1, int(avail_across / lh))
        if len(lines) > mx:  # zusammenfassen, wenn es nicht passt
            joined = " · ".join(t for t, _ in parts)
            lines = [(ln, "400") for ln in _wrap_w(joined, avail_len, size)][:mx]
        x0 = x + w / 2 - (len(lines) - 1) * lh / 2 + size * 0.35
        for i, (ln, wt) in enumerate(lines):
            s.append(f'<text transform="translate({x0+i*lh:.2f} {y+h-1.2:.2f}) rotate(-90)" font-size="{size:.2f}" font-weight="{wt}" fill="#000">{esc(ln)}</text>')
    else:
        lines = []
        for txt, wt in parts:
            for ln in _wrap_w(txt, w - 2, size):
                lines.append((ln, wt))
        mx = max(1, int((h - top - 1) / lh))
        lines = lines[:mx]
        y0 = y + top + (h - top - len(lines) * lh) / 2 + size
        for i, (ln, wt) in enumerate(lines):
            s.append(f'<text x="{x+w/2:.2f}" y="{y0+i*lh:.2f}" font-size="{size:.2f}" font-weight="{wt}" text-anchor="middle" fill="#000">{esc(ln)}</text>')
    return "".join(s)


def label_pages(cfg, name, raw_opts=None, lang="de"):
    """Liefert A4-Querformat-Seiten (SVG, 1 Einheit = 1 mm) mit einem Streifen je belegter Reihe."""
    o = label_opts(raw_opts)
    g = layout(cfg)
    k = o["module"] / TE
    pw, ph, mx, top, bottom = 297.0, 210.0, 12.0, 24.0, 14.0
    strips = []
    for r in g["rows"]:
        cells = [(c["item"], c["w"] * k) for c in r["items"]]
        if not any(_label_cell(it, 0, 0, w, o["height"], o) for it, w in cells):
            continue
        part, used, n = [], 0.0, 0
        for it, w in cells:
            if part and used + w > pw - 2 * mx - 10:
                strips.append((r["idx"] + 1, n, part))
                part, used, n = [], 0.0, n + 1
            part.append((it, w))
            used += w
        strips.append((r["idx"] + 1, n, part))
    pages, body, y = [], [], top
    for row, n, part in strips:
        if y + o["height"] > ph - bottom and body:
            pages.append("".join(body))
            body, y = [], top
        body.append(f'<text x="{mx:.2f}" y="{y+o["height"]/2+1:.2f}" font-size="2.6" fill="#888">{tr("row", lang)[0]}{row}{"abcdef"[n] if n else ""}</text>')
        x = mx + 10
        for it, w in part:
            body.append(_label_cell(it, x, y, w, o["height"], o))
            x += w
        y += o["height"] + o["gap"]
    if body or not pages:
        pages.append("".join(body))
    out = []
    for i, b in enumerate(pages):
        head = (f'<text x="{mx}" y="10" font-size="4" font-weight="700" fill="#111">{esc(tr("lbl_title", lang))} · {esc(name)}</text>'
                f'<text x="{mx}" y="15.5" font-size="2.6" fill="#555">{esc(tr("lbl_hint", lang))}</text>'
                f'<rect x="{pw-mx-100}" y="8" width="100" height="1.2" fill="#111"/><text x="{pw-mx}" y="13.5" font-size="2.6" text-anchor="end" fill="#555">100 mm</text>'
                f'<text x="{pw-mx}" y="{ph-6}" font-size="2.6" fill="#888" text-anchor="end">{tr("page", lang)} {i+1} / {len(pages)}</text>')
        out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}mm" height="{ph}mm" viewBox="0 0 {pw} {ph}" {FONT}>'
                   f'<rect width="{pw}" height="{ph}" fill="#fff"/>{head}{b}</svg>')
    return out


def labels_pdf(cfg, name, raw_opts=None, lang="de"):
    return _merge(label_pages(cfg, name, raw_opts, lang), f"{tr('lbl_title', lang)} {name}")
