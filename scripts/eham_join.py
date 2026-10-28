#!/usr/bin/env python3
"""Join eHam review ratings (data/ham/raw/eham_ratings.json) onto ham feature records as top-level `rating`.

  eham_join.py            -> writes rating {avg, n, pid, last, name} into data/ham/features/*.json, prints match stats
Match rule: a catalog model token (alnum run with a digit and a letter, ≥3 chars, hyphens/spaces collapsed) must appear
in the eHam product name's tokens, and the brand must agree when the eHam name names a known brand. Among several eHam
rows, the one with the most reviews wins (variants like "-ASP" share their base model's reviews).
"""
import glob, json, re, sys
from pathlib import Path

D = Path(__file__).parent.parent / "data/ham"
E = json.load(open(D / "raw/eham_ratings.json"))
tok = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def toks(s):
    ws = [w for w in re.split(r"[^A-Za-z0-9]+", s or "") if w]
    ok = lambda w: re.search(r"\d", w) and re.search(r"[A-Za-z]", w) and len(w) >= 3
    t = {tok(w) for w in ws if ok(w)}
    t |= {tok(a + b) for a, b in zip(ws, ws[1:]) if ok(a + b) and len(a) <= 4}     # "FT 991A", "IC-7300" → ft991a, ic7300
    return t


def num(s):
    m = re.search(r"\(([\d.]+)\)", s or "")
    return float(m.group(1)) if m else None


rows = []
for r in E["rows"]:
    td = r["td"]
    n = int(td[1]) if len(td) > 1 and td[1].isdigit() else 0
    rows.append({"pid": r["pid"], "name": r["name"], "n": n, "last": td[2] if len(td) > 2 else None, "msrp": td[3] if len(td) > 3 else None,
                 "avg": num(td[-1]), "cat": r["cat"], "t": toks(r["name"]), "lname": r["name"].lower()})
idx = {}
for r in rows:
    for t in r["t"]:
        idx.setdefault(t, []).append(r)
BRANDS = {b.lower() for b in ["Yaesu", "Icom", "Kenwood", "Elecraft", "FlexRadio", "Flex", "Diamond", "Comet", "MFJ", "Hy-Gain", "Hygain", "Cushcraft",
                              "Chameleon", "Alpha", "Buddipole", "Par", "Hustler", "DX Engineering", "Moonraker", "Kelemen", "InnovAntennas", "Momobeam",
                              "DIEX", "REZ", "Larsen", "M2", "OptiBeam", "SteppIR", "Butternut", "Comtek", "Bushcomm", "Alinco", "Nagoya", "Arrow"]}
stats = {"radio": [0, 0], "antenna": [0, 0]}
for fn in sorted(glob.glob(str(D / "features/*.json"))):
    p = json.load(open(fn))
    kind = p.get("kind") or "radio"
    stats[kind][1] += 1
    mine = toks(p.get("name", "")) | toks(p.get("title", ""))
    brand = (p.get("brand") or "").lower().split()[0] if p.get("brand") else ""
    cands = {id(r): r for t in mine for r in idx.get(t, [])}.values()
    # brand must agree if the eHam name starts with some other known brand
    good = [r for r in cands if not (any(r["lname"].startswith(b) for b in BRANDS) and brand and not r["lname"].startswith(brand[:4]))]
    good = [r for r in good if r["avg"] is not None and r["n"] > 0]
    old = p.pop("rating", None)
    if good:
        best = max(good, key=lambda r: r["n"])
        p["rating"] = {"avg": best["avg"], "n": best["n"], "pid": best["pid"], "last": best["last"], "name": best["name"]}
        stats[kind][0] += 1
    if p.get("rating") != old:
        json.dump(p, open(fn, "w"), ensure_ascii=False, indent=1)
for k, (a, b) in stats.items():
    print(f"{k}: {a}/{b} matched to eHam", file=sys.stderr)
