"""Plausibilitäts- und Normhinweise (DE/EN). Hinweise blockieren nie – Abweichen ist erlaubt."""
from .render import layout, TE

PROT = ("ls", "rcbo", "afdd")


def stats(cfg):
    g = layout(cfg)
    total = sum(r["width"] for r in g["rows"])
    used = sum(r["used"] for r in g["rows"])
    return dict(total_te=round(total / TE, 1), used_te=round(used / TE, 1), free_te=round((total - used) / TE, 1),
                rows=[dict(idx=r["idx"], used_te=round(r["used"] / TE, 2), total_te=round(r["width"] / TE, 2)) for r in g["rows"]])


def run_checks(cfg, lang="de"):
    en = lang == "en"
    g = layout(cfg)
    items = cfg.get("items", [])
    by_id = {i["id"]: i for i in items}
    out = []

    def add(cid, level, de, eng, norm="", ids=()):
        out.append(dict(id=cid, level=level, text=eng if en else de, norm=norm, items=list(ids)))

    # --- Maßhaltigkeit (immer aktiv)
    for r in g["rows"]:
        if r["used"] > r["width"] + 0.01:
            n, u, w, te = r["idx"] + 1, r["used"], r["width"], r["width"] / TE
            add(f"overflow:{r['idx']}", "error",
                f"Reihe {n} ist überbelegt: {u:.1f} mm belegt, {w:.1f} mm ({te:g} TE) verfügbar.",
                f"Row {n} is overfilled: {u:.1f} mm used, {w:.1f} mm ({te:g} modules) available.",
                "Dimensions" if en else "Maßhaltigkeit", [o["item"]["id"] for o in r["items"]])
    for r in g["rows"]:
        if r["blocked_by"] is not None and r["items"]:
            a, b = r["idx"] + 1, r["blocked_by"] + 1
            add(f"meterblock:{r['idx']}", "error",
                f"Reihe {a} wird vom Zähler in Reihe {b} überdeckt, enthält aber Geräte.",
                f"Row {a} is covered by the meter in row {b} but contains devices.",
                "Dimensions" if en else "Maßhaltigkeit", [o["item"]["id"] for o in r["items"]])
        for o in r["items"]:
            if o["item"]["dev"].get("category") == "meter" and o["y"] + o["h"] > g["H"] - 6:
                add(f"meterfit:{o['item']['id']}", "error",
                    f"Der Zähler in Reihe {r['idx']+1} ragt unten aus dem Schrank ({o['h']:g} mm hoch).",
                    f"The meter in row {r['idx']+1} extends beyond the bottom of the enclosure ({o['h']:g} mm high).",
                    "Dimensions" if en else "Maßhaltigkeit", [o["item"]["id"]])
    if not cfg.get("norm_checks", True):
        return _mark(out, cfg)

    def cat(i):
        return i["dev"].get("category")

    def name(i):
        return i.get("tag") or i["dev"].get("article") or ("Device" if en else "Gerät")

    doc = "Documentation" if en else "Dokumentation"
    ls = [i for i in items if cat(i) in PROT]
    rcds = [i for i in items if cat(i) == "rcd"]

    for i in ls:
        nm = name(i)
        if cat(i) == "ls" and (i["dev"].get("current_a") or 0) <= 32:
            r = by_id.get(i.get("rcd_id") or "")
            if not r:
                add(f"norcd:{i['id']}", "warn",
                    f"{nm} ist keinem FI-Schutzschalter zugeordnet. Steckdosenstromkreise bis 32 A und Beleuchtungsstromkreise in Wohnungen brauchen einen Fehlerstromschutz mit höchstens 30 mA.",
                    f"{nm} is not assigned to an RCD. Socket circuits up to 32 A and lighting circuits in dwellings need residual current protection of 30 mA or less.",
                    "DIN VDE 0100-410", [i["id"]])
            elif (r["dev"].get("rcd_ma") or 0) > 30:
                ma = r["dev"].get("rcd_ma")
                add(f"rcdma:{i['id']}", "warn",
                    f"{nm} hängt an einem FI mit {ma} mA; für den Personenschutz sind höchstens 30 mA vorgesehen.",
                    f"{nm} is fed by an RCD with {ma} mA; personal protection calls for 30 mA or less.",
                    "DIN VDE 0100-410", [i["id"], r["id"]])
        if (i["dev"].get("poles") or 1) == 1 and not i.get("phase"):
            add(f"nophase:{i['id']}", "info", f"{nm}: Außenleiter (L1/L2/L3) nicht zugeordnet.", f"{nm}: phase (L1/L2/L3) not assigned.", doc, [i["id"]])
        if not (i.get("function") or i.get("room")):
            add(f"nolabel:{i['id']}", "info",
                f"{nm} ist nicht beschriftet (Funktion/Raum). Stromkreise müssen eindeutig gekennzeichnet sein.",
                f"{nm} has no label (function/room). Circuits must be clearly identified.",
                "DIN VDE 0100-510", [i["id"]])

    # --- Belastung je FI
    for r in rcds:
        nm = name(r)
        kids = [i for i in ls if i.get("rcd_id") == r["id"]]
        if not kids:
            add(f"rcdempty:{r['id']}", "info", f"{nm}: keine Stromkreise zugeordnet.", f"{nm}: no circuits assigned.", doc, [r["id"]])
            continue
        load = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
        unk = 0.0
        for k in kids:
            a = float(k["dev"].get("current_a") or 0)
            multi = (k["dev"].get("poles") or 1) >= 3 or k.get("phase") == "L1-L3"
            if multi:
                for p in load:
                    load[p] += a
            elif k.get("phase") in load:
                load[k["phase"]] += a
            else:
                unk += a
        rin = float(r["dev"].get("current_a") or 0)
        rpoles = r["dev"].get("poles") or 2
        if rpoles <= 2:
            worst, where = sum(load.values()) + unk, ("total" if en else "gesamt")
            if any((k["dev"].get("poles") or 1) >= 3 for k in kids):
                add(f"rcdpoles:{r['id']}", "error", f"{nm} ist 2-polig, ihm sind aber 3-polige Stromkreise zugeordnet.",
                    f"{nm} is 2-pole but has 3-pole circuits assigned.", "Plausibility" if en else "Plausibilität", [r["id"]])
        else:
            p = max(load, key=load.get)
            worst, where = load[p] + unk / 3, p
        if rin and worst > rin:
            add(f"rcdload:{r['id']}", "warn",
                f"{nm} ({rin:g} A): Summe der nachgeschalteten LS-Nennströme ({where}) beträgt {worst:g} A. Der FI muss gegen Überlast geschützt sein – über die Vorsicherung oder einen begründeten Gleichzeitigkeitsfaktor.",
                f"{nm} ({rin:g} A): the rated currents of the downstream breakers ({where}) add up to {worst:g} A. The RCD must be protected against overload, by the upstream fuse or a justified diversity factor.",
                "DIN VDE 0100-530", [r["id"]] + [k["id"] for k in kids])

    n_circuits = len([i for i in ls if cat(i) == "ls"])
    if n_circuits >= 2 and len(rcds) == 1 and not any(cat(i) in ("rcbo", "afdd") for i in items):
        add("onercd", "warn",
            "Alle Stromkreise hängen an einem einzigen FI. Die Stromkreise sollen so auf mehrere Fehlerstrom-Schutzeinrichtungen verteilt werden, dass eine Auslösung nicht die gesamte Anlage abschaltet.",
            "All circuits depend on a single RCD. Circuits should be spread over several RCDs so that one trip does not switch off the whole installation.",
            "DIN 18015-1 / DIN VDE 0100-530", [r["id"] for r in rcds])

    # --- Phasenverteilung
    ph = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    for i in ls:
        if (i["dev"].get("poles") or 1) < 3 and i.get("phase") in ph:
            ph[i["phase"]] += float(i["dev"].get("current_a") or 0)
    if sum(ph.values()) and max(ph.values()) - min(ph.values()) > 32:
        lst = ", ".join(f"{k} {v:g} A" for k, v in ph.items())
        add("phasebal", "info", f"Ungleichmäßige Aufteilung auf die Außenleiter: {lst} (Summe der LS-Nennströme).",
            f"Uneven distribution across the phases: {lst} (sum of breaker ratings).", "DIN 18015-1", [])

    if items and not any(cat(i) == "spd" for i in items):
        add("nospd", "warn",
            "Kein Überspannungsschutz eingeplant. In neuen oder erweiterten Anlagen ist er gefordert; er kann auch im Zählerschrank sitzen.",
            "No surge protection planned. It is required in new or extended installations; it may also sit in the meter cabinet.",
            "DIN VDE 0100-443 / -534", [])

    tags = {}
    for i in items:
        if i.get("tag"):
            tags.setdefault(i["tag"], []).append(i["id"])
    for t, ids in tags.items():
        if len(ids) > 1:
            add(f"duptag:{t}", "warn", f"Die Kennzeichnung „{t}“ ist {len(ids)}-mal vergeben.", f"The designation “{t}” is used {len(ids)} times.", "DIN EN 81346", ids)

    st = stats(cfg)
    if items and st["total_te"] and st["free_te"] / st["total_te"] < 0.2:
        add("reserve", "info", f"Nur {st['free_te']:g} von {st['total_te']:g} TE frei. Für spätere Erweiterungen wird eine Platzreserve empfohlen.",
            f"Only {st['free_te']:g} of {st['total_te']:g} modules free. Spare space is recommended for later extensions.", "DIN 18015-2", [])
    if g["n_rows"] * g["fields"] < 4:
        add("minrows", "info", "Stromkreisverteiler in Mehrraumwohnungen sollen mindestens 4-reihig sein (Einraumwohnung: 3-reihig).",
            "Distribution boards in multi-room dwellings should have at least 4 rows (one-room dwelling: 3 rows).", "DIN 18015-2", [])
    return _mark(out, cfg)


def _mark(out, cfg):
    ign = set(cfg.get("ignored", []))
    for c in out:
        c["ignored"] = c["id"] in ign
    order = {"error": 0, "warn": 1, "info": 2}
    out.sort(key=lambda c: (c["ignored"], order[c["level"]]))
    return out
