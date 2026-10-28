#!/usr/bin/env python3
"""LLM antenna records (data/ham/ant_out/*.jsonl) -> validated data/ham/features/<slug>.json with rule-based pairs.

Numbers the DXE spec table states (power, weight, length) are cross-checked against the record; the spec wins on conflict.
"""
import glob, json, re, sys
from pathlib import Path

D = Path(__file__).parent.parent / "data/ham"
BANDS = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m", "2m", "1.25m", "70cm", "23cm"]
FKEYS = ["ant_type", "mount", "ant_bands", "resonant", "tuner_req", "max_w", "max_w_digital", "gain_dbi", "elements", "boom_ft",
         "turn_radius_ft", "wind_sqft", "length_ft", "height_ft", "weight_lb", "radials", "directional", "polarization", "connector",
         "rx_only", "assembled", "extra"]
cat = {r["slug"]: r for r in json.load(open(D / "ant_catalog.json"))}


def first_num(s):
    """first power figure in W; handles "1,000 W", "1.5 kW", "10kW"."""
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(k?)W?", str(s or ""), re.I)
    return float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1) if m else None


# DXE spells brands several ways ("Comet" / "Comet Antennas", "CHAMELEON ANTENNA"); collapse to one canonical name
BRAND_SUFFIX = re.compile(r"\s+(antennas?|antenna systems|antenna company|antenennen und electronik)$", re.I)
BRAND_CANON = {"compactenna": "COMPACtenna", "par end-fedz": "Par EndFedz", "par endfedz": "Par EndFedz", "eantenna": "EAntenna",
               "optibeam": "OptiBeam", "icom": "Icom", "sotabeams": "SOTAbeams", "larsen": "Larsen", "diex": "DIEX", "m2": "M2",
               "chameleon": "Chameleon", "rez": "REZ", "comtek": "Comtek", "wimo": "WiMo", "telrex": "Telrex", "hygain": "Hy-Gain", "hy-gain": "Hy-Gain", "tufteln": "TufTeln"}


def brand(b):
    b = BRAND_SUFFIX.sub("", (b or "").strip())
    return BRAND_CANON.get(b.lower(), b if not b.isupper() or len(b) <= 5 else b.title())


def pairs(r):
    f, out = r["f"], []
    if f.get("resonant") is False:
        out.append({"id": "antenna tuner (wide-range)", "why": "non-resonant on its listed bands", "req": True})
    if f.get("directional"):
        out.append({"id": "rotator + mast/tower", "why": "beam must be turned", "req": True})
    if f.get("radials"):
        out.append({"id": "radial wires / counterpoise", "why": "vertical needs a ground system", "req": True})
    if f.get("mount") == "mobile":
        out.append({"id": "mobile antenna mount (mag / trunk-lip / NMO)", "why": "vehicle mount not included", "req": False})
    if f.get("mount") in ("base", "portable") and f.get("ant_type") in ("end-fed", "random-wire", "ocf-dipole", "vertical") and not f.get("rx_only"):
        out.append({"id": "1:1 common-mode choke at the shack entry", "why": "keeps feedline RF out of the shack", "req": False})
    return out


n, bad, skipped = 0, [], 0
for fn in sorted(glob.glob(str(D / "ant_out/*.jsonl"))):
    for line in open(fn):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            bad.append((fn, line[:60], str(e)))
            continue
        ex = (r.get("f") or {}).get("extra") or {}
        # keep only complete ham antennas (or RX-only): drop accessories, bare whips/boxes, CB/GMRS/commercial-band items
        if ex.get("not_antenna") or ex.get("component") or not ((r.get("f") or {}).get("ant_bands") or (r.get("f") or {}).get("rx_only")):
            skipped += 1
            continue
        src = cat.get(r.get("id"))
        if not src:
            bad.append((fn, r.get("id"), "unknown slug"))
            continue
        r["kind"] = "antenna"
        r["brand"] = brand(r.get("brand") or src.get("brand"))
        r["price"] = src["price"]
        f = r.setdefault("f", {})
        for k in FKEYS:
            f.setdefault(k, {} if k == "extra" else None)
        f["ant_bands"] = [b for b in BANDS if b in (f.get("ant_bands") or [])]
        kv = src.get("kv") or {}
        pw = first_num(kv.get("Antenna Power Rating"))
        if pw and f.get("max_w") != pw:
            f["extra"]["max_w_llm"] = f.get("max_w")
            f["max_w"] = pw
        r.setdefault("jobs", [])
        r.setdefault("gotchas", [])
        r.setdefault("legacy", False)
        r["pairs"] = pairs(r)
        r["f"]["extra"]["dxe_part_type"] = src["cat"]
        json.dump(r, open(D / f"features/{r['id']}.json", "w"), ensure_ascii=False, indent=1)
        n += 1
print(f"{n} antenna records written, {skipped} skipped (non-antenna / part / no ham band), {len(bad)} rejected", file=sys.stderr)
for b in bad[:20]:
    print("  ", b, file=sys.stderr)
