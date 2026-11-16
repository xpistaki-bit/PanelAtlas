"""Maßstäbliche SVG-Darstellung eines Verteilers (1 SVG-Einheit = 1 mm)."""
import base64
import html
import pathlib

TE = 17.5
CAP = 45.0  # Ausschnitt der Abdeckung nach DIN 43880

CAT_LABEL = {"ls": "LS-Schalter", "rcd": "FI-Schalter", "rcbo": "FI/LS", "afdd": "Brandschutzschalter", "spd": "Überspannungsschutz",
             "switch": "Schalter", "terminal": "Reihenklemme", "hlak": "Hauptleitungsabzweigklemme", "relay": "Schaltgerät",
             "meter": "Zähler", "blank": "Leerplatz", "other": "Sonstiges"}
MODULAR = {"ls", "rcd", "rcbo", "afdd", "spd", "switch", "relay", "other", "blank"}
HL_COL = {"gr": "#8f9499", "": "#8f9499", "bl": "#2f6fd0", "blue": "#2f6fd0", "pe": "#3f9b3f", "br": "#7a4a22", "brown": "#7a4a22", "sw": "#2a2a2a", "black": "#2a2a2a"}
PEN_DEFAULT = ("top", "bottom")
ACT_COL = {"black": "#2b2b2b", "grey": "#7a7f85", "white": "#f7f7f7", "red": "#c62828", "blue": "#1e63b5", "green": "#2e9e3f", "yellow": "#f2c200", "orange": "#f57c00"}
MARK_COL = {"red": "#ff1744", "yellow": "#ffea00", "magenta": "#ff00e5", "cyan": "#00e5ff"}
# Hintergrund / Schriftfarbe der Beschriftungsfelder
LABEL_COL = {"yellow": ("#fff176", "#111"), "orange": ("#ffb74d", "#111"), "red": ("#e53935", "#fff"), "pink": ("#f48fb1", "#111"), "purple": ("#8e44ad", "#fff"),
             "blue": ("#1e88e5", "#fff"), "lightblue": ("#90caf9", "#111"), "cyan": ("#4dd0e1", "#111"), "green": ("#43a047", "#fff"), "lime": ("#dce775", "#111"),
             "brown": ("#8d6e63", "#fff"), "grey": ("#cfd8dc", "#111")}
PHASE_COLOR = {"L1": "#8b5a2b", "L2": "#222222", "L3": "#777777", "L1-L3": "#b0452c"}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def geometry(cfg):
    e = cfg["enclosure"]
    rows, fields = int(e["rows"]), int(e.get("fields", 1))
    W, H = float(e["width_mm"]), float(e["height_mm"])
    pitch = float(e.get("row_pitch_mm", 125))
    row_w = float(e.get("te_per_row", 12)) * TE
    field_w = W / fields
    top = (H - (rows - 1) * pitch) / 2
    out = []
    for f in range(fields):
        for r in range(rows):
            out.append(dict(idx=f * rows + r, field=f, r=r, x0=f * field_w + (field_w - row_w) / 2, cy=top + r * pitch, width=row_w))
    return dict(W=W, H=H, pitch=pitch, rows=out, field_w=field_w, n_rows=rows, fields=fields)


def layout(cfg):
    """Ordnet die Geräte je Reihe lückenlos von links an. Liefert Geometrie inkl. Positionen.

    Zähler sind höher als eine Reihe: sie hängen oben in ihrer Reihe und belegen die Reihen darunter mit
    (row["blocked_by"] = Index der Reihe, deren Zähler hineinragt)."""
    g = geometry(cfg)
    pitch = g["pitch"]
    for row in g["rows"]:
        row["items"], row["used"], row["span"], row["blocked_by"] = [], 0.0, 0, None
    for it in cfg.get("items", []):
        idx = it.get("row", 0)
        if not 0 <= idx < len(g["rows"]):
            idx = 0
        row = g["rows"][idx]
        w = float(it["dev"].get("width_mm", TE))
        h = float(it["dev"].get("height_mm", 85))
        y = row["cy"] - h / 2
        if it["dev"].get("category") == "meter" and h > pitch - 8:
            y = row["cy"] - 40
            row["span"] = max(row["span"], int(-(-(y + h + 18 - (row["cy"] + pitch / 2)) // pitch)))
        row["items"].append(dict(item=it, x=row["x0"] + row["used"], w=w, h=h, y=y, cy=row["cy"], pos=len(row["items"]) + 1))
        row["used"] += w
    for row in g["rows"]:
        for k in range(1, row["span"] + 1):
            if row["r"] + k < g["n_rows"]:
                g["rows"][row["idx"] + k]["blocked_by"] = row["idx"]
    return g


def pen_positions(cfg):
    v = cfg["enclosure"].get("pen_blocks")
    return list(PEN_DEFAULT) if v is None else [p for p in v if p in ("top", "middle", "bottom")]


def _fit(text, width, size):
    n = max(1, int(width / (size * 0.56)))
    text = str(text or "")
    return text if len(text) <= n else text[: max(1, n - 1)] + "…"


def _image_href(name, media_dir, embed):
    if not name:
        return None
    p = pathlib.Path(media_dir) / pathlib.Path(name).name
    if not p.exists():
        return None
    if embed:
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return "/media/" + p.name


def _device(o, media_dir, embed):
    it, x, w, h = o["item"], o["x"], o["w"], o["h"]
    d = it["dev"]
    cat = d.get("category", "other")
    cy = o["cy"]
    y = o.get("y", cy - h / 2)
    s = []
    href = _image_href(d.get("image"), media_dir, embed)
    if href:
        s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#fff"/>')
        s.append(f'<image x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" preserveAspectRatio="none" href="{href}" xlink:href="{href}"/>')
        s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="#777" stroke-width="0.25"/>')
        return "".join(s)
    if cat == "blank":
        s.append(f'<rect x="{x:.2f}" y="{cy-CAP/2:.2f}" width="{w:.2f}" height="{CAP}" fill="#e9e9e4" stroke="#aaa" stroke-width="0.25" stroke-dasharray="1.5 1"/>')
        return "".join(s)
    if cat == "terminal":
        col = d.get("color") or ""
        if col == "pe":
            s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h/2:.2f}" fill="#3f9b3f"/>')
            s.append(f'<rect x="{x:.2f}" y="{y+h/2:.2f}" width="{w:.2f}" height="{h/2:.2f}" fill="#e8d21d"/>')
        else:
            s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{"#2f6fd0" if col == "blue" else "#a3a8ad"}"/>')
        s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="#555" stroke-width="0.2"/>')
        r = min(w * 0.3, 1.6)
        for yy in (y + h * 0.18, y + h * 0.82):
            s.append(f'<circle cx="{x+w/2:.2f}" cy="{yy:.2f}" r="{r:.2f}" fill="#e6e6e6" stroke="#444" stroke-width="0.15"/>')
        s.append(f'<rect x="{x+w*0.2:.2f}" y="{cy-2.2:.2f}" width="{w*0.6:.2f}" height="4.4" fill="#fff" opacity="0.85"/>')
        return "".join(s)
    if cat == "hlak":
        n = max(1, int(d.get("poles") or 1))
        pcs = d.get("pole_colors") or [d.get("color") or ""] * n
        pw = w / n
        names = ["L1", "L2", "L3", "N", "PE"] if n > 1 else [{"blue": "N", "pe": "PE"}.get(d.get("color") or "", "")]
        for i in range(n):
            px = x + i * pw
            c = pcs[i] if i < len(pcs) else ""
            if c == "pe":
                s.append(f'<rect x="{px:.2f}" y="{y:.2f}" width="{pw:.2f}" height="{h/2:.2f}" fill="#3f9b3f"/><rect x="{px:.2f}" y="{y+h/2:.2f}" width="{pw:.2f}" height="{h/2:.2f}" fill="#e8d21d"/>')
            else:
                s.append(f'<rect x="{px:.2f}" y="{y:.2f}" width="{pw:.2f}" height="{h:.2f}" fill="{HL_COL.get(c, "#8f9499")}"/>')
            if i:
                s.append(f'<line x1="{px:.2f}" y1="{y:.2f}" x2="{px:.2f}" y2="{y+h:.2f}" stroke="#333" stroke-width="0.3"/>')
            for yy in (y + h * 0.2, y + h * 0.8):
                for xx in ((px + pw * 0.3, px + pw * 0.7) if pw > 14 else (px + pw / 2,)):
                    s.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="{min(pw*0.16,3):.2f}" fill="#d9d9d9" stroke="#333" stroke-width="0.2"/>')
            nm = {"bl": "N", "blue": "N", "pe": "PE"}.get(c)
            if nm is None:
                uniform = len(set(pcs)) == 1
                nm = names[i] if n > 1 and i < len(names) and (uniform or i < 3) else ""
            if nm:
                s.append(f'<text x="{px+pw/2:.2f}" y="{cy+1.6:.2f}" font-size="{min(4.5, pw*0.3):.2f}" text-anchor="middle" fill="#fff" stroke="#000" stroke-opacity="0.35" stroke-width="0.15" font-weight="700">{nm}</text>')
        s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="1" fill="none" stroke="#333" stroke-width="0.35"/>')
        return "".join(s)
    if cat == "meter":
        return _meter(d, x, y, w, h)

    # Reiheneinbaugerät: Sockel + 45-mm-Kappe
    body = "#efefeb"
    s.append(f'<rect x="{x+0.15:.2f}" y="{y:.2f}" width="{w-0.3:.2f}" height="{h:.2f}" rx="0.8" fill="#dcdcd6" stroke="#8a8a84" stroke-width="0.25"/>')
    s.append(f'<rect x="{x+0.15:.2f}" y="{cy-CAP/2:.2f}" width="{w-0.3:.2f}" height="{CAP}" fill="{body}" stroke="#8a8a84" stroke-width="0.25"/>')
    poles = max(1, int(d.get("poles") or 1))
    n_mod = max(1, round(w / TE))
    for i in range(1, n_mod):
        px = x + i * w / n_mod
        s.append(f'<line x1="{px:.2f}" y1="{y:.2f}" x2="{px:.2f}" y2="{y+h:.2f}" stroke="#b5b5ae" stroke-width="0.2"/>')
    # Klemmschrauben oben/unten
    for i in range(n_mod):
        px = x + (i + 0.5) * w / n_mod
        for yy in (y + (h - CAP) / 4, y + h - (h - CAP) / 4):
            s.append(f'<circle cx="{px:.2f}" cy="{yy:.2f}" r="2.4" fill="#c9c9c2" stroke="#777" stroke-width="0.2"/>')
            s.append(f'<line x1="{px-1.6:.2f}" y1="{yy:.2f}" x2="{px+1.6:.2f}" y2="{yy:.2f}" stroke="#666" stroke-width="0.35"/>')
    man = d.get("manufacturer", "")
    s.append(f'<text x="{x+w/2:.2f}" y="{cy-CAP/2+4:.2f}" font-size="2.6" text-anchor="middle" fill="#444" font-weight="700">{esc(_fit(man, w-1, 2.6))}</text>')
    rating = ""
    if d.get("current_a"):
        rating = f'{d.get("characteristic") or ""}{d["current_a"]:g}' + ("" if d.get("characteristic") else " A")
    look = d.get("look")
    if isinstance(look, dict) and look.get("actuator"):
        s.append(_look(look, x, cy, w, rating))
        s.append(f'<text x="{x+w/2:.2f}" y="{cy+CAP/2-1.6:.2f}" font-size="2.4" text-anchor="middle" fill="#555">{esc(_fit(d.get("article", ""), w-1, 2.4))}</text>')
        return "".join(s)
    if cat in ("ls", "rcbo", "afdd", "switch", "relay", "other"):
        lw = min(w - 5, 9 if poles == 1 or w < 30 else w - 8)
        lever = {"ls": "#2b2b2b", "rcbo": "#2b2b2b", "afdd": "#2b2b2b", "switch": "#c62828", "relay": "#666", "other": "#666"}[cat]
        s.append(f'<rect x="{x+w/2-lw/2:.2f}" y="{cy-11:.2f}" width="{lw:.2f}" height="11" rx="1" fill="{lever}"/>')
        s.append(f'<text x="{x+w/2:.2f}" y="{cy+8:.2f}" font-size="{5 if w > 16 else 3.4}" text-anchor="middle" font-weight="700" fill="#111">{esc(rating)}</text>')
        if cat in ("rcbo", "afdd"):
            s.append(f'<rect x="{x+w-7:.2f}" y="{cy+11:.2f}" width="5" height="4" rx="0.6" fill="{"#f2c200" if cat == "afdd" else "#1e63b5"}"/>')
            s.append(f'<text x="{x+3:.2f}" y="{cy+15:.2f}" font-size="2.6" fill="#333">{d.get("rcd_ma") or ""}{" mA" if d.get("rcd_ma") else "AFDD"}</text>')
    elif cat == "rcd":
        lw = min(w - 8, 14)
        s.append(f'<rect x="{x+w/2-lw/2:.2f}" y="{cy-11:.2f}" width="{lw:.2f}" height="11" rx="1" fill="#1e63b5"/>')
        s.append(f'<rect x="{x+w-9:.2f}" y="{cy+3:.2f}" width="6" height="5" rx="0.8" fill="#f2c200" stroke="#8a6d00" stroke-width="0.2"/>')
        s.append(f'<text x="{x+w-6:.2f}" y="{cy+7:.2f}" font-size="3" text-anchor="middle" font-weight="700">T</text>')
        s.append(f'<text x="{x+3:.2f}" y="{cy+8:.2f}" font-size="4.6" font-weight="700" fill="#111">{esc(rating)}</text>')
        s.append(f'<text x="{x+3:.2f}" y="{cy+14:.2f}" font-size="3.2" fill="#222">{d.get("rcd_ma") or ""} mA  Typ {esc(d.get("rcd_type") or "")}</text>')
    elif cat == "spd":
        red = man.upper().startswith("DEHN")
        for i in range(n_mod):
            px = x + i * w / n_mod
            s.append(f'<rect x="{px+1.2:.2f}" y="{cy-CAP/2+6:.2f}" width="{w/n_mod-2.4:.2f}" height="{CAP-14}" rx="0.8" fill="{"#c8102e" if red else "#f7f7f4"}" stroke="#777" stroke-width="0.2"/>')
            s.append(f'<rect x="{px+w/n_mod/2-2:.2f}" y="{cy-4:.2f}" width="4" height="4" fill="#2e9e3f"/>')
        s.append(f'<text x="{x+w/2:.2f}" y="{cy+CAP/2-5.4:.2f}" font-size="3" text-anchor="middle" fill="#222" font-weight="700">SPD</text>')
    s.append(f'<text x="{x+w/2:.2f}" y="{cy+CAP/2-1.6:.2f}" font-size="2.4" text-anchor="middle" fill="#555">{esc(_fit(d.get("article", ""), w-1, 2.4))}</text>')
    return "".join(s)


def _symbol(kind, cx, cy, z):
    """Kleines Schaltzeichen, Mittelpunkt (cx, cy), Größe z."""
    st = 'fill="none" stroke="#333" stroke-width="0.35" stroke-linecap="round"'
    h = z / 2
    if kind in ("relay", "contactor"):
        o = (f'<rect x="{cx-h:.2f}" y="{cy-h*0.35:.2f}" width="{z*0.42:.2f}" height="{h*0.7:.2f}" {st}/>'
             f'<path d="M{cx-h+z*0.21:.2f} {cy-h:.2f}V{cy-h*0.35:.2f}M{cx-h+z*0.21:.2f} {cy+h*0.35:.2f}V{cy+h:.2f}" {st}/>'
             f'<path d="M{cx+h*0.55:.2f} {cy-h:.2f}V{cy-h*0.4:.2f}M{cx+h*0.55:.2f} {cy+h:.2f}V{cy+h*0.4:.2f}L{cx+h*0.05:.2f} {cy-h*0.35:.2f}" {st}/>'
             f'<path d="M{cx-h+z*0.42:.2f} {cy:.2f}H{cx+h*0.3:.2f}" {st} stroke-dasharray="0.6 0.5"/>')
        if kind == "contactor":
            o += f'<path d="M{cx+h:.2f} {cy-h:.2f}V{cy-h*0.4:.2f}M{cx+h:.2f} {cy+h:.2f}V{cy+h*0.4:.2f}L{cx+h*0.5:.2f} {cy-h*0.35:.2f}" {st}/>'
        return o
    if kind == "timer":
        return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{h*0.9:.2f}" {st}/><path d="M{cx:.2f} {cy-h*0.55:.2f}V{cy:.2f}L{cx+h*0.4:.2f} {cy+h*0.25:.2f}" {st}/>'
    if kind == "bell":
        return (f'<path d="M{cx-h*0.8:.2f} {cy+h*0.45:.2f}H{cx+h*0.8:.2f}M{cx-h*0.6:.2f} {cy+h*0.45:.2f}A{h*0.6:.2f} {h*0.95:.2f} 0 0 1 {cx+h*0.6:.2f} {cy+h*0.45:.2f}" {st}/>'
                f'<circle cx="{cx:.2f}" cy="{cy+h*0.7:.2f}" r="{h*0.14:.2f}" fill="#333"/>')
    if kind == "transformer":
        return f'<circle cx="{cx:.2f}" cy="{cy-h*0.3:.2f}" r="{h*0.55:.2f}" {st}/><circle cx="{cx:.2f}" cy="{cy+h*0.3:.2f}" r="{h*0.55:.2f}" {st}/>'
    if kind == "socket":
        return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{h*0.9:.2f}" {st}/><circle cx="{cx-h*0.35:.2f}" cy="{cy:.2f}" r="{h*0.13:.2f}" fill="#333"/>'
                f'<circle cx="{cx+h*0.35:.2f}" cy="{cy:.2f}" r="{h*0.13:.2f}" fill="#333"/>')
    if kind == "lamp":
        return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{h*0.85:.2f}" {st}/><path d="M{cx-h*0.6:.2f} {cy-h*0.6:.2f}L{cx+h*0.6:.2f} {cy+h*0.6:.2f}M{cx+h*0.6:.2f} {cy-h*0.6:.2f}L{cx-h*0.6:.2f} {cy+h*0.6:.2f}" {st}/>'
    return ""


def _look(look, x, cy, w, rating):
    """Frei gestaltete Front eines Reiheneinbaugeräts (Katalog → Darstellung)."""
    s = []
    col = ACT_COL.get(look.get("actuator_color") or "grey", "#7a7f85")
    edge = "#888" if col == "#f7f7f7" else "none"
    pos = look.get("actuator_pos") or "center"
    off = min(5.0, w * 0.27)
    ax = {"left": x + off, "right": x + w - off}.get(pos, x + w / 2)
    act = look.get("actuator")
    t1, t2 = str(look.get("text1") or ""), str(look.get("text2") or "")
    if t1:
        s.append(f'<text x="{x+w/2:.2f}" y="{cy-CAP/2+7.2:.2f}" font-size="2.3" text-anchor="middle" fill="#222" font-weight="700">{esc(_fit(t1, w-1, 2.3))}</text>')
    if t2:
        s.append(f'<text x="{x+w/2:.2f}" y="{cy-CAP/2+10:.2f}" font-size="2.1" text-anchor="middle" fill="#333">{esc(_fit(t2, w-1, 2.1))}</text>')
    ay = cy - 1.5
    if act == "lever":
        lw = min(w - 5, 9) if pos == "center" else min(w * 0.4, 7)
        s.append(f'<rect x="{ax-lw/2:.2f}" y="{ay-6:.2f}" width="{lw:.2f}" height="11" rx="1" fill="{col}" stroke="{edge}" stroke-width="0.25"/>')
    elif act == "slide":
        s.append(f'<rect x="{ax-2.2:.2f}" y="{ay-6.5:.2f}" width="4.4" height="13" rx="0.6" fill="#e2e2dd" stroke="#8a8a84" stroke-width="0.25"/>')
        s.append(f'<rect x="{ax-1.6:.2f}" y="{ay-5.9:.2f}" width="3.2" height="6" rx="0.5" fill="{col}" stroke="{edge}" stroke-width="0.25"/>')
        tx = ax + 3.6 if pos != "right" else ax - 3.6
        s.append(f'<text x="{tx:.2f}" y="{ay-3.6:.2f}" font-size="2.2" text-anchor="middle" fill="#333">I</text><text x="{tx:.2f}" y="{ay+6:.2f}" font-size="2.2" text-anchor="middle" fill="#333">0</text>')
    elif act == "button":
        s.append(f'<circle cx="{ax:.2f}" cy="{ay:.2f}" r="3.4" fill="{col}" stroke="#555" stroke-width="0.3"/>')
    elif act == "rotary":
        s.append(f'<circle cx="{ax:.2f}" cy="{ay:.2f}" r="4.2" fill="#e2e2dd" stroke="#666" stroke-width="0.3"/><rect x="{ax-0.9:.2f}" y="{ay-4:.2f}" width="1.8" height="8" rx="0.6" fill="{col}" stroke="{edge}" stroke-width="0.2"/>')
    sym = look.get("symbol")
    centered = pos == "center" and act != "none"
    if sym:
        z = min(8.0, w * 0.42)
        if centered:
            s.append(_symbol(sym, x + w / 2, cy + 8.5, min(z, 6.5)))
        else:
            sx = x + w - off - 0.6 if pos == "left" else (x + off + 0.6 if pos == "right" else x + w / 2)
            s.append(_symbol(sym, sx, ay, z))
    if rating and look.get("show_rating", True) and not (sym and centered):
        s.append(f'<text x="{x+w/2:.2f}" y="{cy+9:.2f}" font-size="{5 if w > 30 else 3.2}" text-anchor="middle" font-weight="700" fill="#111">{esc(rating)}</text>')
    if look.get("window"):
        s.append(f'<rect x="{x+2:.2f}" y="{cy+10.6:.2f}" width="{w-4:.2f}" height="8" rx="0.8" fill="#bfe6e8" fill-opacity="0.85" stroke="#6fb0b6" stroke-width="0.3"/>')
    led = look.get("led")
    if led in ACT_COL:
        s.append(f'<circle cx="{x+w-3.2:.2f}" cy="{cy-CAP/2+6.4:.2f}" r="1.3" fill="{ACT_COL[led]}" stroke="#555" stroke-width="0.2"/>')
    return "".join(s)


def _overlay(o):
    """Markierungen je eingesetztem Gerät: Signalfarbe und Kennzeichen für zwei angeschlossene Leiter."""
    it, x, y, w, h = o["item"], o["x"], o["y"], o["w"], o["h"]
    s = []
    if str(it.get("wires") or "1") == "2" and it["dev"].get("category") in ("ls", "rcbo", "afdd"):
        bx, by = x + w / 2, y + h - (h - CAP) / 4
        s.append(f'<rect x="{bx-4.6:.2f}" y="{by-2.6:.2f}" width="9.2" height="5.2" rx="1.2" fill="#ff9100" stroke="#8a4b00" stroke-width="0.3"/>'
                 f'<text x="{bx:.2f}" y="{by+1.35:.2f}" font-size="3.6" text-anchor="middle" font-weight="700" fill="#111">2×</text>')
    mc = MARK_COL.get(it.get("mark") or "")
    if mc:
        s.append(f'<rect x="{x+0.8:.2f}" y="{y+0.8:.2f}" width="{w-1.6:.2f}" height="{h-1.6:.2f}" rx="1" fill="{mc}" fill-opacity="0.22" stroke="{mc}" stroke-width="1.6"/>'
                 f'<path d="M{x+w-0.8:.2f} {y+0.8:.2f}v{min(9, w*0.5):.2f}l-{min(9, w*0.5):.2f} -{min(9, w*0.5):.2f}z" fill="{mc}" stroke="#222" stroke-width="0.2"/>')
    return "".join(s)


def device_preview_svg(dev, media_dir=None):
    """Einzelnes Gerät als SVG (Vorschau im Katalog)."""
    w, h = float(dev.get("width_mm") or TE), float(dev.get("height_mm") or 85)
    o = dict(item=dict(dev=dev, id="p"), x=4.0, w=w, h=h, y=4.0, cy=4.0 + h / 2)
    body = _device(o, media_dir or "/nonexistent", False)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {w+8:.2f} {h+8:.2f}" '
            f'font-family="DejaVu Sans, Arial, Helvetica, sans-serif"><rect width="{w+8:.2f}" height="{h+8:.2f}" fill="#ecece6"/>'
            f'<rect x="0" y="{4+h/2-17.5:.2f}" width="{w+8:.2f}" height="35" fill="#c9ccd0"/>{body}</svg>')


def _meter(d, x, y, w, h):
    """Zähler: mME (Display), Ferraris (Zählwerk + Läuferscheibe), iMSys (mME + Gateway)."""
    mt = d.get("meter_type") or "mme"
    s = []

    def ehz(ex, ew, title):
        o = [f'<rect x="{ex:.2f}" y="{y:.2f}" width="{ew:.2f}" height="{h:.2f}" rx="3" fill="#e9eaec" stroke="#5c6066" stroke-width="0.5"/>',
             f'<rect x="{ex+ew*0.1:.2f}" y="{y+h*0.14:.2f}" width="{ew*0.8:.2f}" height="{h*0.24:.2f}" rx="1.5" fill="#1d2b24" stroke="#444" stroke-width="0.3"/>',
             f'<text x="{ex+ew*0.86:.2f}" y="{y+h*0.14+h*0.17:.2f}" font-size="{min(ew*0.13, h*0.12):.2f}" text-anchor="end" fill="#9df5b5" font-family="DejaVu Sans Mono, monospace" font-weight="700">012345</text>',
             f'<text x="{ex+ew*0.86:.2f}" y="{y+h*0.14+h*0.225:.2f}" font-size="{min(ew*0.05, 4):.2f}" text-anchor="end" fill="#9df5b5">kWh</text>',
             f'<circle cx="{ex+ew*0.22:.2f}" cy="{y+h*0.52:.2f}" r="{min(ew*0.06, 6):.2f}" fill="#30343a" stroke="#888" stroke-width="0.3"/>',
             f'<circle cx="{ex+ew*0.78:.2f}" cy="{y+h*0.52:.2f}" r="{min(ew*0.035, 3):.2f}" fill="#c62828"/>',
             f'<rect x="{ex+ew*0.1:.2f}" y="{y+h*0.64:.2f}" width="{ew*0.8:.2f}" height="{h*0.2:.2f}" fill="#fff" stroke="#999" stroke-width="0.25"/>',
             f'<text x="{ex+ew/2:.2f}" y="{y+h*0.72:.2f}" font-size="{min(ew*0.085, 7):.2f}" text-anchor="middle" font-weight="700" fill="#222">{title}</text>',
             f'<text x="{ex+ew/2:.2f}" y="{y+h*0.8:.2f}" font-size="{min(ew*0.05, 4):.2f}" text-anchor="middle" fill="#555">3x230/400 V · 5(60) A</text>']
        return "".join(o)

    if mt == "ferraris":
        s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="5" fill="#2b2d31" stroke="#111" stroke-width="0.6"/>')
        s.append(f'<rect x="{x+w*0.08:.2f}" y="{y+h*0.06:.2f}" width="{w*0.84:.2f}" height="{h*0.5:.2f}" rx="3" fill="#dfe3e6" stroke="#777" stroke-width="0.4"/>')
        dw = w * 0.085
        for i in range(7):
            dx = x + w * 0.2 + i * dw * 1.05
            s.append(f'<rect x="{dx:.2f}" y="{y+h*0.14:.2f}" width="{dw:.2f}" height="{dw*1.4:.2f}" fill="{"#c62828" if i == 6 else "#111"}"/>')
            s.append(f'<text x="{dx+dw/2:.2f}" y="{y+h*0.14+dw*1.05:.2f}" font-size="{dw*0.95:.2f}" text-anchor="middle" fill="#fff" font-weight="700">{(i*3+1)%10}</text>')
        s.append(f'<text x="{x+w*0.2+7*dw*1.05:.2f}" y="{y+h*0.14+dw*2.1:.2f}" font-size="{dw*0.55:.2f}" text-anchor="end" fill="#222">kWh</text>')
        s.append(f'<rect x="{x+w*0.16:.2f}" y="{y+h*0.36:.2f}" width="{w*0.68:.2f}" height="{h*0.022:.2f}" fill="#b9bdc2" stroke="#666" stroke-width="0.25"/>')
        s.append(f'<rect x="{x+w*0.46:.2f}" y="{y+h*0.36:.2f}" width="{w*0.07:.2f}" height="{h*0.022:.2f}" fill="#c62828"/>')
        s.append(f'<text x="{x+w/2:.2f}" y="{y+h*0.47:.2f}" font-size="{w*0.05:.2f}" text-anchor="middle" fill="#333">Drehstromzähler · 10(60) A</text>')
        s.append(f'<rect x="{x+w*0.08:.2f}" y="{y+h*0.72:.2f}" width="{w*0.84:.2f}" height="{h*0.22:.2f}" rx="2" fill="#3a3d42" stroke="#111" stroke-width="0.4"/>')
        for i in range(2):
            s.append(f'<circle cx="{x+w*(0.2+0.6*i):.2f}" cy="{y+h*0.83:.2f}" r="{w*0.025:.2f}" fill="#9aa0a6" stroke="#222" stroke-width="0.3"/>')
        s.append(f'<text x="{x+w/2:.2f}" y="{y+h*0.66:.2f}" font-size="{w*0.07:.2f}" text-anchor="middle" fill="#fff" font-weight="700">kME</text>')
    elif mt == "imsys":
        s.append(ehz(x, w / 2, "mME"))
        gx, gw = x + w / 2, w / 2
        s.append(f'<rect x="{gx:.2f}" y="{y:.2f}" width="{gw:.2f}" height="{h:.2f}" rx="3" fill="#d5dde6" stroke="#5c6066" stroke-width="0.5"/>')
        s.append(f'<rect x="{gx+gw*0.1:.2f}" y="{y+h*0.14:.2f}" width="{gw*0.8:.2f}" height="{h*0.3:.2f}" rx="1.5" fill="#1e3a5f"/>')
        s.append(f'<text x="{gx+gw/2:.2f}" y="{y+h*0.3:.2f}" font-size="{gw*0.15:.2f}" text-anchor="middle" fill="#fff" font-weight="700">SMGW</text>')
        s.append(f'<text x="{gx+gw/2:.2f}" y="{y+h*0.38:.2f}" font-size="{gw*0.055:.2f}" text-anchor="middle" fill="#cfe1f5">Smart-Meter-Gateway</text>')
        for i, c in enumerate(("#2e9e3f", "#2e9e3f", "#f2c200", "#9aa0a6")):
            s.append(f'<circle cx="{gx+gw*(0.2+0.2*i):.2f}" cy="{y+h*0.56:.2f}" r="{gw*0.03:.2f}" fill="{c}"/>')
        for i in range(3):
            s.append(f'<rect x="{gx+gw*(0.14+0.26*i):.2f}" y="{y+h*0.7:.2f}" width="{gw*0.2:.2f}" height="{h*0.12:.2f}" rx="1" fill="#30343a"/>')
    else:
        s.append(ehz(x, w, "mME"))
    return "".join(s)


def _pen_bar(x, y, w, h, kind, vertical=False):
    col, txt = ("#3f9b3f", "PE") if kind == "pe" else ("#2f6fd0", "N")
    o = [f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="1.2" fill="{col}" stroke="#3a3a3a" stroke-width="0.3"/>']
    if kind == "pe":
        o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w if vertical else w:.2f}" height="{h:.2f}" rx="1.2" fill="none" stroke="#e8d21d" stroke-width="0.9" stroke-dasharray="3 3"/>')
    length = h if vertical else w
    n = max(2, int((length - 14) / 7))
    for i in range(n):
        t = 12 + (length - 16) * i / max(1, n - 1)
        cx, cy = (x + w / 2, y + t) if vertical else (x + t, y + h / 2)
        o.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="1.9" fill="#d8d8d8" stroke="#444" stroke-width="0.2"/>')
    tx, ty = (x + w / 2, y + 7) if vertical else (x + 5.5, y + h / 2 + 1.6)
    o.append(f'<text x="{tx:.2f}" y="{ty:.2f}" font-size="4.2" text-anchor="middle" fill="#fff" font-weight="700">{txt}</text>')
    return "".join(o)


def pen_blocks_svg(cfg, g):
    """PE/N-Klemmenblöcke des Schranks (oben / Mitte / unten) je Feld. Liefert (svg, y der unteren Blöcke)."""
    pos = pen_positions(cfg)
    if not pos:
        return "", None
    H, pitch, fw, n = g["H"], g["pitch"], g["field_w"], g["n_rows"]
    out, bottom_y = {"top": [], "middle": [], "bottom": []}, None
    for f in range(g["fields"]):
        first, last = g["rows"][f * n], g["rows"][f * n + n - 1]
        x0, rw = first["x0"], first["width"]
        half = rw / 2 - 3
        if "top" in pos:
            y = max(9.0, first["cy"] - 45 - 8 - 14)
            out["top"].append(_pen_bar(x0, y, half, 14, "pe") + _pen_bar(x0 + rw - half, y, half, 14, "n"))
        if "bottom" in pos:
            bottom_y = min(H - 9 - 14, last["cy"] + pitch / 2 + 4)
            out["bottom"].append(_pen_bar(x0, bottom_y, half, 14, "pe") + _pen_bar(x0 + rw - half, bottom_y, half, 14, "n"))
        if "middle" in pos:
            margin = x0 - f * fw
            if margin >= 26:
                ln = min(140.0, H - 60)
                out["middle"].append(_pen_bar(f * fw + 10, H / 2 - ln / 2, 12, ln, "pe", True) + _pen_bar((f + 1) * fw - 22, H / 2 - ln / 2, 12, ln, "n", True))
    return "".join(f'<g class="pen" data-pen="{k}">{"".join(v)}</g>' for k, v in out.items() if v), bottom_y


def _label(o, y0, sh, k=1.0):
    """Beschriftungsfeld unter dem Gerät. k = Schriftfaktor (cfg.view.label_scale)."""
    it, x, w = o["item"], o["x"], o["w"]
    cat = it["dev"].get("category")
    tag, fn, room = it.get("tag", ""), it.get("function", ""), it.get("room", "")
    if cat == "blank" or not (tag or fn or room):
        return ""
    bg, fg = LABEL_COL.get(it.get("label_color") or "", ("#fff", "#111"))
    s = [f'<rect x="{x+0.3:.2f}" y="{y0:.2f}" width="{w-0.6:.2f}" height="{sh:.2f}" fill="{bg}" stroke="#9a9a94" stroke-width="0.2"/>']
    ph = it.get("phase")
    if ph in PHASE_COLOR:
        s.append(f'<rect x="{x+0.3:.2f}" y="{y0:.2f}" width="{w-0.6:.2f}" height="1.4" fill="{PHASE_COLOR[ph]}"/>')
    if w >= 30:
        lines = [(tag, 4.2 * k, "700"), (fn, 3.3 * k, "400"), (room, 3.3 * k, "400")]
        yy = y0 + 2.2 + 4.2 * k
        for txt, size, wt in lines:
            if txt and yy < y0 + sh:
                s.append(f'<text x="{x+w/2:.2f}" y="{yy:.2f}" font-size="{size:.2f}" text-anchor="middle" font-weight="{wt}" fill="{fg}">{esc(_fit(txt, w-2, size))}</text>')
                yy += size + 1.6
    else:
        cols = [(tag, "700"), (fn, "400"), (room, "400")]
        cols = [c for c in cols if c[0]]
        if w < 15:
            cols = [(" ".join(c[0] for c in cols), "700" if tag else "400")]
        step = (w - 1) / len(cols)
        size = min((3.1 if w >= 15 else 2.6) * k, step * 0.8)
        for i, (txt, wt) in enumerate(cols):
            cx = x + 0.5 + step * (i + 0.5) + size * 0.35
            s.append(f'<text transform="translate({cx:.2f} {y0+sh-1.2:.2f}) rotate(-90)" font-size="{size:.2f}" font-weight="{wt}" fill="{fg}">{esc(_fit(txt, sh-3, size))}</text>')
    return "".join(s)


def label_scale(cfg):
    try:
        return min(2.5, max(0.7, float(cfg.get("view", {}).get("label_scale") or 1.3)))
    except (TypeError, ValueError):
        return 1.3


def render_svg(cfg, media_dir, embed=False, standalone=True, crop=None):
    g = layout(cfg)
    W, H, pitch = g["W"], g["H"], g["pitch"]
    cover = bool(cfg.get("view", {}).get("cover"))
    k = label_scale(cfg)
    m = 12
    s = []
    vb = crop or (-m, -m, W + 2 * m, H + 2 * m)
    attrs = f'viewBox="{vb[0]:.2f} {vb[1]:.2f} {vb[2]:.2f} {vb[3]:.2f}" font-family="DejaVu Sans, Arial, Helvetica, sans-serif"'
    if standalone:
        attrs += f' width="{W+2*m:.2f}mm" height="{H+2*m:.2f}mm"'
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" {attrs}>')
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="4" fill="#f7f7f3" stroke="#6b6b66" stroke-width="1"/>')
    s.append(f'<rect x="6" y="6" width="{W-12}" height="{H-12}" rx="2" fill="#ecece6" stroke="#b9b9b2" stroke-width="0.4"/>')
    for f in range(1, g["fields"]):
        fx = f * g["field_w"]
        s.append(f'<line x1="{fx:.2f}" y1="6" x2="{fx:.2f}" y2="{H-6}" stroke="#b9b9b2" stroke-width="0.6"/>')
    pen_svg, pen_bottom = pen_blocks_svg(cfg, g)
    # 1. Durchgang: Reihen (Trefferfläche, Hutschiene, Beschriftung der Reihe)
    for row in g["rows"]:
        x0, cy, rw = row["x0"], row["cy"], row["width"]
        over = row["used"] > rw + 0.01
        s.append(f'<g class="row" data-row="{row["idx"]}">')
        s.append(f'<rect class="rowhit" data-row="{row["idx"]}" x="{row["field"]*g["field_w"]+7:.2f}" y="{cy-pitch/2+1:.2f}" width="{g["field_w"]-14:.2f}" height="{pitch-2:.2f}" fill="#000" fill-opacity="0"/>')
        s.append(f'<rect x="{x0-6:.2f}" y="{cy-17.5:.2f}" width="{rw+12:.2f}" height="35" fill="#c9ccd0" stroke="#8b8f94" stroke-width="0.3"/>')
        s.append(f'<rect x="{x0-6:.2f}" y="{cy-12:.2f}" width="{rw+12:.2f}" height="24" fill="#b5b9be"/>')
        for t in range(int(rw / TE) + 1):
            tx = x0 + t * TE
            s.append(f'<line x1="{tx:.2f}" y1="{cy+17.5:.2f}" x2="{tx:.2f}" y2="{cy+(21 if t % 2 == 0 else 19.5):.2f}" stroke="#777" stroke-width="0.25"/>')
        col = "#c62828" if over else "#666"
        s.append(f'<text x="{x0-8:.2f}" y="{cy-19.5:.2f}" font-size="4" fill="#666" text-anchor="end">R{row["idx"]+1}</text>')
        s.append(f'<text x="{x0+rw+8:.2f}" y="{cy-19.5:.2f}" font-size="3.4" fill="{col}" font-weight="{700 if over else 400}">{row["used"]/TE:.1f}/{rw/TE:g} TE</text>')
        s.append("</g>")
    s.append(pen_svg)
    # 2. Durchgang: Geräte, Abdeckung, Beschriftungsfelder (Zähler ragen über Folgereihen)
    for row in g["rows"]:
        x0, cy, rw = row["x0"], row["cy"], row["width"]
        over = row["used"] > rw + 0.01
        normal = [o for o in row["items"] if o["item"]["dev"].get("category") != "meter"]
        maxh = max([o["h"] for o in normal] or [85])
        has_mod = any(o["item"]["dev"].get("category") in MODULAR for o in row["items"]) or not row["items"]
        for o in row["items"]:
            it = o["item"]
            s.append(f'<g class="item" data-id="{esc(it["id"])}" data-row="{row["idx"]}" data-x="{o["x"]:.2f}" data-w="{o["w"]:.2f}">')
            s.append(_device(o, media_dir, embed))
            s.append(_overlay(o))
            s.append("</g>")
        if cover and has_mod and row["blocked_by"] is None and not row["span"]:
            ya, yb = cy - pitch / 2 + 1.5, cy + pitch / 2 - 1.5
            fx0, fx1 = row["field"] * g["field_w"] + 9, (row["field"] + 1) * g["field_w"] - 9
            s.append(f'<path fill-rule="evenodd" pointer-events="none" fill="#fbfbf8" stroke="#a9a9a2" stroke-width="0.35" d="M{fx0:.2f} {ya:.2f}H{fx1:.2f}V{yb:.2f}H{fx0:.2f}Z M{x0:.2f} {cy-CAP/2:.2f}V{cy+CAP/2:.2f}H{x0+rw:.2f}V{cy-CAP/2:.2f}Z"/>')
            y0, sh = cy + CAP / 2 + 2, pitch / 2 - CAP / 2 - 6
        else:
            y0 = cy + maxh / 2 + 1
            sh = max(8.0, pitch - maxh - 3)
            if not normal or all(o["item"]["dev"].get("category") in ("terminal", "hlak") for o in normal):
                sh = min(sh, 30)
        if pen_bottom is not None and row["r"] == g["n_rows"] - 1:
            sh = max(8.0, min(sh, pen_bottom - 1.5 - y0))
        for o in row["items"]:
            if o["item"]["dev"].get("category") == "meter":
                lab = _label(o, o["y"] + o["h"] + 1, min(16.0 * k, 26), k)
            else:
                lab = _label(o, y0, sh, k)
            if lab:
                s.append(f'<g class="lbl" data-id="{esc(o["item"]["id"])}">{lab}</g>')
        if over:
            s.append(f'<rect x="{x0+rw:.2f}" y="{cy-maxh/2-2:.2f}" width="{row["used"]-rw:.2f}" height="{maxh+4:.2f}" fill="#c62828" fill-opacity="0.25" stroke="#c62828" stroke-width="0.5" pointer-events="none"/>')
    s.append("</svg>")
    return "".join(s)
