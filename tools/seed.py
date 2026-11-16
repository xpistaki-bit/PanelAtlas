#!/usr/bin/env python3
"""Erzeugt app/catalog_seed.json (Startkatalog).

Aufruf:  python3 -I tools/seed.py [hager-katalog.txt]
Mit Katalogtext werden Hager-Artikelnummern gegen den Katalog geprüft;
nicht gefundene Nummern werden verworfen.
"""
import json, re, sys, pathlib

TE = 17.5
hager_txt = pathlib.Path(sys.argv[1]).read_text(errors="ignore") if len(sys.argv) > 1 else None
out = []
dropped = []


def hager_ok(art):
    if hager_txt is None:
        return True
    ok = re.search(r"\b%s\b" % re.escape(art), hager_txt) is not None
    if not ok:
        dropped.append(art)
    return ok


def enc(man, series, art, name, h, w, d, rows, fields=1, te=12, pitch=125, mount="AP", verified=True, order_no="", note="", pen_blocks=("top", "bottom")):
    out.append(dict(kind="enclosure", manufacturer=man, series=series, article=art, name=name, data=dict(
        height_mm=h, width_mm=w, depth_mm=d, rows=rows, fields=fields, te_per_row=te, row_pitch_mm=pitch,
        mount=mount, verified=verified, order_no=order_no, note=note, pen_blocks=list(pen_blocks))))


def dev(man, series, art, name, cat, te=None, width_mm=None, height_mm=85, poles=1, current_a=None, char="",
        rcd_ma=None, rcd_type="", color="", verified=True, note="", **extra):
    w = width_mm if width_mm is not None else te * TE
    out.append(dict(kind="device", manufacturer=man, series=series, article=art, name=name, data=dict(
        category=cat, width_mm=round(w, 2), height_mm=height_mm, poles=poles, current_a=current_a,
        characteristic=char, rcd_ma=rcd_ma, rcd_type=rcd_type, color=color, verified=verified, note=note, **extra)))


# ---------------------------------------------------------------- Schränke
# ABB ComfortLine Compact CA (Aufputz). Maße: ABB/Striebel & John Katalog bzw. Konformitätserklärung.
ca_h = {3: 500, 4: 650, 5: 800, 6: 950, 7: 1100, 8: 1250}
ca_w = {1: 300, 2: 550, 3: 800, 4: 1050}
ca_order = {"CA13": "2CPX052142R9999", "CA14": "2CPX052143R9999", "CA15": "2CPX052144R9999", "CA16": "2CPX052145R9999",
            "CA24": "2CPX052149R9999", "CA25": "2CPX052150R9999", "CA26": "2CPX052151R9999", "CA27": "2CPX052152R9999",
            "CA28": "2CPX052153R9999", "CA34": "2CPX052154R9999", "CA35": "2CPX052155R9999", "CA36": "2CPX052156R9999",
            "CA37": "2CPX052157R9999"}
for f, rws in ((1, (3, 4, 5, 6, 7)), (2, (4, 5, 6, 7, 8)), (3, (4, 5, 6, 7))):
    for r in rws:
        t = f"CA{f}{r}"
        enc("ABB", "ComfortLine Compact CA", t, f"Kleinverteiler Aufputz, {f} Feld{'er' if f > 1 else ''}, {r} Reihen, {f*r*12} PLE",
            ca_h[r], ca_w[f], 160, r, f, order_no=ca_order.get(t, ""),
            note="Bestückung mit Verteilerfeldern V angenommen; Ausbauvariante prüfen")
# ABB ComfortLine Compact CU (Unterputz/Hohlwand) – Außenmaße Blendrahmen
enc("ABB", "ComfortLine Compact CU", "CU17V", "Kleinverteiler Unterputz, 1 Feld, 7 Reihen, 84 PLE", 1164, 365, 125, 7, 1, mount="UP", order_no="2CPX052610R9999", note="Außenmaß Blendrahmen")
enc("ABB", "ComfortLine Compact CU", "CU18V", "Kleinverteiler Unterputz, 1 Feld, 8 Reihen, 96 PLE", 1315, 365, 125, 8, 1, mount="UP", order_no="2CPX052611R9999", note="Außenmaß Blendrahmen")
enc("ABB", "ComfortLine Compact CU", "CU23V", "Kleinverteiler Unterputz, 2 Felder, 3 Reihen, 72 PLE", 565, 615, 125, 3, 2, mount="UP", order_no="2CPX052612R9999", note="Außenmaß Blendrahmen")
# ABB UK600 (Unterputz) – Nischenmaße
for art, rows, h, ono in (("UK624N3", 2, 480, "2CPX031370R9999"), ("UK636N3", 3, 605, "2CPX031371R9999"), ("UK648N3", 4, 730, "2CPX031372R9999")):
    enc("ABB", "UK600", art, f"Unterputzverteiler, {rows}-reihig, {rows*12} PLE", h, 367, 95, rows, 1, mount="UP", order_no=ono, note="Maße = Nischenmaß; 12 (14) PLE je Reihe")

# Hager volta
for art, rows, h in (("VA12CN", 1, 245), ("VA24CN", 2, 370), ("VA36CN", 3, 515), ("VA48CN", 4, 640), ("VA60CN", 5, 765)):
    if hager_ok(art):
        enc("Hager", "volta", art, f"Kleinverteiler volta Aufputz, {rows}x12 PLE, IP30", h, 305, 96.5, rows)
for pre, mount, label in (("VU", "UP", "Unterputz"), ("VH", "HW", "Hohlwand")):
    for rows, h in ((1, 356.5), (2, 505.5), (3, 630.5), (4, 755.5), (5, 880.5)):
        art = f"{pre}{rows*12}NC"
        if hager_ok(art):
            enc("Hager", "volta", art, f"Kleinverteiler volta {label}, {rows}x12 PLE, IP30", h, 348, 94.5, rows, mount=mount, note="Außenmaß Blendrahmen")
# Hager univers Feldverteiler Aufputz IP44 (FWB..S), Hutschienenabstand 125 mm
fw_h = {3: 500, 4: 650, 5: 800, 6: 950, 7: 1100}
fw_w = {1: 300, 2: 550, 3: 800}
for r in fw_h:
    for f in fw_w:
        art = f"FWB{r}{f}S"
        if hager_ok(art):
            enc("Hager", "univers Feldverteiler", art, f"AP-Feldverteiler IP44, {f} Feld{'er' if f > 1 else ''}, {r} Reihen, {r*f*12} PLE",
                fw_h[r], fw_w[f], 161, r, f)
# Schneider
enc("Schneider Electric", "Resi9 KV", "R9H10938", "Kleinverteiler Resi9 KV Unterputz, 4x12 Module", 749, 344, 90, 4, 1, mount="UP", note="Außenmaß Rahmen")

# ---------------------------------------------------------------- Geräte
AMPS = (6, 10, 13, 16, 20, 25, 32)
# Hager LS 6 kA
for ch, pre in (("B", "MBN"), ("C", "MCN")):
    for a in AMPS:
        art = f"{pre}1{a:02d}"
        if hager_ok(art):
            dev("Hager", "LS 6 kA", art, f"LS-Schalter {ch}{a}, 1-polig, 6 kA", "ls", te=1, poles=1, current_a=a, char=ch)
    for a in AMPS:
        art = f"{pre}3{a:02d}"
        if hager_ok(art):
            dev("Hager", "LS 6 kA", art, f"LS-Schalter {ch}{a}, 3-polig, 6 kA", "ls", te=3, poles=3, current_a=a, char=ch)
# Hager FI Typ A
for art, p, a in (("CDA240D", 2, 40), ("CDA263D", 2, 63), ("CDA440D", 4, 40), ("CDA463D", 4, 63)):
    if hager_ok(art):
        dev("Hager", "FI Typ A", art, f"FI-Schutzschalter {p}-polig, {a} A, 30 mA, Typ A", "rcd", te=p, poles=p, current_a=a, rcd_ma=30, rcd_type="A")
# Hager FI/LS 1P+N
for a in (6, 10, 13, 16, 20):
    art = f"ADS9{a:02d}D"
    if hager_ok(art):
        dev("Hager", "FI/LS", art, f"FI/LS-Schalter B{a}, 1P+N, 30 mA, Typ A, 6 kA", "rcbo", te=2, poles=2, current_a=a, char="B", rcd_ma=30, rcd_type="A")
for a in (10, 13, 16):
    art = f"ARC9{a:02d}D"
    if hager_ok(art):
        dev("Hager", "AFDD", art, f"Brandschutzschalter mit LS B{a}, 1P+N", "afdd", te=2, poles=2, current_a=a, char="B", verified=False, note="Breite laut Bestellhilfe 2 PLE, bitte prüfen")
for art, p, a, te in (("SBN340", 3, 40, 3), ("SBN363", 3, 63, 3), ("SBN440", 4, 40, 4), ("SBN463", 4, 63, 4), ("SH363N", 3, 63, 2.5)):
    if hager_ok(art):
        dev("Hager", "Ausschalter", art, f"Ausschalter {p}-polig, {a} A", "switch", te=te, poles=p, current_a=a)
if hager_ok("SPB413"):
    dev("Hager", "Überspannungsschutz", "SPB413", "Überspannungsableiter Typ 2, 4P, 40 kA, TT/TN-S", "spd", te=4, poles=4, verified=False, note="Breite 4 PLE angenommen, bitte prüfen")
if hager_ok("SPA412"):
    dev("Hager", "Überspannungsschutz", "SPA412", "Kombiableiter Typ 1+2+3, 4P, TN-S/TT, 12,5 kA, mit FM", "spd", te=4, poles=4)
if hager_ok("KH35A"):
    dev("Hager", "Hauptleitungsabzweigklemme", "KH35A", "Hauptleitungsabzweigklemme 4-polig, 35 mm², 100 A", "hlak", width_mm=96, height_mm=49, poles=4, current_a=100)
if hager_ok("KH35L3"):
    dev("Hager", "Hauptleitungsabzweigklemme", "KH35L3", "Hauptleitungsabzweigklemme 3-polig, 35 mm², 100 A", "hlak", width_mm=71, height_mm=55, poles=3, current_a=100)
if hager_ok("KH35N"):
    dev("Hager", "Hauptleitungsabzweigklemme", "KH35N", "Hauptleitungsabzweigklemme 1-polig N, blau, 100 A", "hlak", width_mm=27, height_mm=55, poles=1, current_a=100, color="blue")
if hager_ok("EPN510"):
    dev("Hager", "Schaltgeräte", "EPN510", "Fernschalter (Stromstoß) 1 Schließer, 230 V, 16 A", "relay", te=1, current_a=16)
if hager_ok("ESC225"):
    dev("Hager", "Schaltgeräte", "ESC225", "Installationsschütz 25 A, 2 Schließer, 230 V", "relay", te=1, poles=2, current_a=25, verified=False, note="Breite bitte prüfen")

# ABB (Typbezeichnungen; Maße nach DIN 43880, nicht einzeln gegen Katalog geprüft)
for ch in ("B", "C"):
    for a in AMPS:
        dev("ABB", "S200", f"S201-{ch}{a}", f"LS-Schalter {ch}{a}, 1-polig, 6 kA", "ls", te=1, poles=1, current_a=a, char=ch, verified=False)
    for a in (16, 20, 25, 32):
        dev("ABB", "S200", f"S203-{ch}{a}", f"LS-Schalter {ch}{a}, 3-polig, 6 kA", "ls", te=3, poles=3, current_a=a, char=ch, verified=False)
for p in (2, 4):
    for a in (25, 40, 63):
        dev("ABB", "F200", f"F20{p} A-{a}/0,03", f"FI-Schutzschalter {p}-polig, {a} A, 30 mA, Typ A", "rcd", te=p, poles=p, current_a=a, rcd_ma=30, rcd_type="A", verified=False)
for a in (10, 13, 16):
    dev("ABB", "DS201", f"DS201 A-B{a}/0,03", f"FI/LS-Schalter B{a}, 1P+N, 30 mA, Typ A", "rcbo", te=2, poles=2, current_a=a, char="B", rcd_ma=30, rcd_type="A", verified=False)
dev("ABB", "OVR", "OVR T2 3N 40-275 P QS", "Überspannungsableiter Typ 2, 3P+N, 40 kA", "spd", te=4, poles=4, verified=False)

# Schneider Electric Acti9 (Bestellnummern nach Schema, nicht einzeln geprüft)
for ch, code in (("B", "A9F03"), ("C", "A9F04")):
    for a in AMPS:
        dev("Schneider Electric", "Acti9 iC60N", f"{code}1{a:02d}", f"LS-Schalter iC60N {ch}{a}, 1-polig, 6 kA", "ls", te=1, height_mm=85, poles=1, current_a=a, char=ch, verified=False)
    for a in (16, 20, 25, 32):
        dev("Schneider Electric", "Acti9 iC60N", f"{code}3{a:02d}", f"LS-Schalter iC60N {ch}{a}, 3-polig, 6 kA", "ls", te=3, poles=3, current_a=a, char=ch, verified=False)
for p in (2, 4):
    for a in (25, 40, 63):
        dev("Schneider Electric", "Acti9 iID", f"A9Z21{p}{a}", f"FI-Schutzschalter iID {p}-polig, {a} A, 30 mA, Typ A", "rcd", te=p, poles=p, current_a=a, rcd_ma=30, rcd_type="A", verified=False)

# DEHN
dev("DEHN", "DEHNguard", "952 400", "DEHNguard M TNS 275, Überspannungsableiter Typ 2, TN-S", "spd", te=4, height_mm=90, poles=4)
dev("DEHN", "DEHNguard", "952 310", "DEHNguard M TT 275, Überspannungsableiter Typ 2, TT/TN-S", "spd", te=4, height_mm=90, poles=4, verified=False)
dev("DEHN", "DEHNshield", "941 400", "DEHNshield TNS 255, Kombi-Ableiter Typ 1+2, TN-S", "spd", te=4, height_mm=90, poles=4)
dev("DEHN", "DEHNshield", "941 310", "DEHNshield TT 255, Kombi-Ableiter Typ 1+2, TT/TN-S", "spd", te=4, height_mm=90, poles=4, verified=False)
dev("DEHN", "DEHNventil", "951 400", "DEHNventil M TNS 255, Kombi-Ableiter Typ 1+2, TN-S", "spd", te=8, height_mm=90, poles=4, verified=False)

# Phoenix Contact Reihenklemmen (Breite laut Datenblatt; Länge = Näherungswert)
pt = [("PT 2,5", "3209510", 5.2, 48.5, "", 24, True), ("PT 2,5 BU", "3209523", 5.2, 48.5, "blue", 24, True), ("PT 2,5-PE", "3209536", 5.2, 48.5, "pe", 24, True),
      ("PT 4", "3211757", 6.2, 56, "", 32, False), ("PT 4 BU", "3211760", 6.2, 56, "blue", 32, False), ("PT 4-PE", "3211766", 6.2, 56, "pe", 32, False),
      ("PT 6", "3211813", 8.2, 57.7, "", 41, True), ("PT 6 BU", "3211819", 8.2, 57.7, "blue", 41, True), ("PT 6-PE", "3211822", 8.2, 57.7, "pe", 41, True),
      ("PT 10", "3212120", 10.2, 67.7, "", 57, False), ("PT 10 BU", "3212123", 10.2, 67.7, "blue", 57, False), ("PT 10-PE", "3212131", 10.2, 67.7, "pe", 57, False)]
for name, art, w, h, col, a, ver in pt:
    kind = "Schutzleiterklemme" if col == "pe" else "Durchgangsklemme"
    dev("Phoenix Contact", "CLIPLINE PT", art, f"{name} {kind}, Push-in, {a} A", "terminal", width_mm=w, height_mm=h, current_a=a, color=col, verified=ver,
        note="Länge Näherungswert" + ("" if ver else "; Breite bitte prüfen"))
for name, art, w, a in (("PTI 2,5-PE/L/N", "3213950", 5.2, 24), ("PTI 2,5-L/N", "3213954", 5.2, 24), ("PTI 4-PE/L/N", "3214049", 6.2, 28)):
    dev("Phoenix Contact", "CLIPLINE PTI", art, f"{name} Installationsetagenklemme, {a} A", "terminal", width_mm=w, height_mm=100, current_a=a, verified=False, note="Maße Näherungswerte")
for name, art, w, a in (("UT 4", "3044102", 6.2, 32), ("UT 6", "3044131", 8.2, 41)):
    dev("Phoenix Contact", "CLIPLINE UT", art, f"{name} Durchgangsklemme, Schraubanschluss, {a} A", "terminal", width_mm=w, height_mm=48, current_a=a, verified=False, note="Maße Näherungswerte")

# weitere Hager Hauptleitungsabzweigklemmen (Maße aus Hager-Katalog)
HL = "Hauptleitungsabzweigklemme"
for art, nm, w, h, col, a in (("KH35E", "1-polig PE, 35 mm²", 27, 55, "pe", 100), ("KH35L", "1-polig L, 35 mm²", 27, 55, "", 100),
                              ("KH35E8", "1-polig PE, 35 mm², 8 Klemmstellen", 46, 55, "pe", 100), ("KH35L8", "1-polig L, 35 mm², 8 Klemmstellen", 46, 55, "", 100),
                              ("KH35N8", "1-polig N, 35 mm², 8 Klemmstellen", 46, 55, "blue", 100),
                              ("KH70G", "1-polig L, 70 mm²", 32.8, 60, "", None), ("KH70B", "1-polig N, 70 mm²", 32.8, 60, "blue", None),
                              ("KH70GN", "1-polig PE, 70 mm²", 32.8, 60, "pe", None)):
    if hager_ok(art):
        dev("Hager", HL, art, f"{HL} {nm}", "hlak", width_mm=w, height_mm=h, poles=1, current_a=a, color=col)
if hager_ok("KH45A"):
    dev("Hager", HL, "KH45A", f"{HL} 5-polig, 35 mm², IP20", "hlak", width_mm=135, height_mm=38, poles=5, current_a=100, pole_colors=["gr", "gr", "gr", "bl", "pe"])
if hager_ok("KH23C"):
    dev("Hager", HL, "KH23C", f"{HL} universZ 3-polig, 2x25/2x16 mm²", "hlak", width_mm=69.2, height_mm=65.9, poles=3, current_a=80)
if hager_ok("KH24C"):
    dev("Hager", HL, "KH24C", f"{HL} universZ 4-polig, 2x25/2x16 mm²", "hlak", width_mm=82.4, height_mm=65.9, poles=4, current_a=80)

# f-tronic HLAK (Typ C), Maße aus f-tronic-Datenblättern bzw. Händlerangaben
FT = {"gr": ("grau", ""), "bl": ("blau", "blue"), "pe": ("grün-gelb", "pe"), "br": ("braun", "brown"), "sw": ("schwarz", "black")}
for art, typ, c in (("7110188", "HLAK1p25gr", "gr"), ("7110189", "HLAK1p25bl", "bl"), ("7110190", "HLAK1p25gnge", "pe"), ("7110192", "HLAK1p25sw", "sw")):
    dev("f-tronic", "HLAK 25 mm²", art, f"{typ} {HL} 1-polig, 25 mm², {FT[c][0]}", "hlak", width_mm=17.8, height_mm=49.3, poles=1, current_a=100, color=FT[c][1])
for art, typ, c in (("7110195", "HLAK1p35gr", "gr"), ("7110196", "HLAK1p35bl", "bl"), ("7110197", "HLAK1p35gnge", "pe"), ("7110199", "HLAK1p35sw", "sw"), ("7110198", "HLAK1p35br", "br")):
    dev("f-tronic", "HLAK 35 mm²", art, f"{typ} {HL} 1-polig, 35 mm², {FT[c][0]}", "hlak", width_mm=22.2, height_mm=49.3, poles=1, current_a=125, color=FT[c][1])
for art, typ, n, w, pc, ver in (("7110194", "HLAK3p25gr", 3, 53.7, ["gr"] * 3, True), ("7110193", "HLAK3p25brswgr", 3, 53.7, ["br", "sw", "gr"], False),
                                ("7110233", "HLAK4p25gr", 4, 71.6, ["gr"] * 4, True), ("7110235", "HLAK4p25grbl", 4, 71.6, ["gr", "gr", "gr", "bl"], True),
                                ("7110234", "HLAK4p25grgn", 4, 71.6, ["gr", "gr", "gr", "pe"], True),
                                ("7110236", "HLAK5p25gr", 5, 88.8, ["gr"] * 5, True), ("7110237", "HLAK5p25grblgn", 5, 88.8, ["gr", "gr", "gr", "bl", "pe"], True)):
    dev("f-tronic", "HLAK 25 mm²", art, f"{typ} {HL} {n}-polig, 25 mm²", "hlak", width_mm=w, height_mm=49.3, poles=n, current_a=100, pole_colors=pc, verified=ver,
        note="" if ver else "Maße vom einfarbigen Typ übernommen")
dev("f-tronic", "HLAK 35 mm²", "7110089", f"HLAK4p35gr {HL} 4-polig, 35 mm², grau", "hlak", width_mm=88.8, height_mm=49.3, poles=4, current_a=125, pole_colors=["gr"] * 4,
    verified=False, note="Breite aus 4 x 22,2 mm abgeleitet")
for art, typ, c in (("7110205", "HLAK1p70sw", "sw"), ("7110204", "HLAK1p70br", "br"), ("7110203", "HLAK1p70gnge", "pe")):
    dev("f-tronic", "HLAK 70 mm²", art, f"{typ} {HL} 1-polig, 70 mm², {FT[c][0]}", "hlak", width_mm=32.8, height_mm=63, poles=1, current_a=160, color=FT[c][1],
        verified=False, note="Höhe bitte prüfen")

# Zähler (Zählerfeld). Höher als eine Reihe: belegen die darunterliegenden Reihen mit.
dev("Allgemein", "Zähler", "mME-eHZ", "mME – moderne Messeinrichtung, digitaler Stromzähler (eHZ, Stecktechnik)", "meter", width_mm=90, height_mm=135, poles=4, current_a=60, meter_type="mme")
dev("Allgemein", "Zähler", "mME-3HZ", "mME – moderne Messeinrichtung, digitaler Stromzähler (Dreipunktbefestigung)", "meter", width_mm=175, height_mm=250, poles=4, current_a=60, meter_type="mme",
    verified=False, note="Maße je nach Hersteller, Richtwert")
dev("Allgemein", "Zähler", "kME-Ferraris", "kME – konventioneller Ferraris-Zähler, Drehstrom (Dreipunktbefestigung)", "meter", width_mm=175, height_mm=290, poles=4, current_a=60, meter_type="ferraris",
    verified=False, note="Maße je nach Hersteller, Richtwert")
dev("Allgemein", "Zähler", "iMSys", "iMSys – intelligentes Messsystem / Smart Meter (mME + Smart-Meter-Gateway)", "meter", width_mm=180, height_mm=135, poles=4, current_a=60, meter_type="imsys",
    verified=False, note="eHZ plus Gateway nebeneinander, Richtwert")


# neutrale Elemente
dev("Allgemein", "Platzhalter", "LEER-0,5", "Leerplatz / Abdeckstreifen 0,5 TE", "blank", te=0.5)
dev("Allgemein", "Platzhalter", "LEER-1", "Leerplatz / Abdeckstreifen 1 TE", "blank", te=1)
dev("Allgemein", "Platzhalter", "ENDHALTER", "Endhalter für Reihenklemmen (ca. 9,5 mm)", "terminal", width_mm=9.5, height_mm=45, verified=False)

dest = pathlib.Path(__file__).resolve().parent.parent / "app" / "catalog_seed.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f"{len(out)} Einträge -> {dest}")
if dropped:
    print("nicht im Hager-Katalog gefunden, verworfen:", ", ".join(dropped))
