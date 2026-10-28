#!/usr/bin/env python3
"""DXE antenna scrape (dxe_antennas.json) -> data/ham/ant_catalog.json + compact shards for LLM normalization.

  ant_prep.py dxe_antennas.json N_SHARDS
Specs come from the DXE spec table when present, else from the overview's "Key: | value" pairs.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKIP = re.compile(r"^(Brand|Manufacturer's Part Number|Part Type|Product Line|DXE Part Number|Item Number|Quantity|UPC|Overview)$")


def kv(r):
    o = dict(r.get("specs") or {})
    parts = [x.strip() for x in (r.get("ov") or "").split("|") if x.strip()]
    i = 0
    while i < len(parts) - 1:
        if parts[i].endswith(":"):
            o.setdefault(parts[i][:-1], parts[i + 1])
            i += 2
        else:
            i += 1
    return o


def money(s):
    try:
        return float(str(s).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


src = json.load(open(sys.argv[1]))
recs = list(src["rec"].values()) if isinstance(src, dict) and "rec" in src else src
n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
cat, compact = [], []
for r in recs:
    o = kv(r)
    price = money(r.get("price")) or money(r.get("list"))
    cat.append({**r, "price": price, "kv": o})
    if not price:
        continue
    compact.append({"slug": r["slug"], "cat": r["cat"], "name": r.get("name"), "brand": r.get("brand") or o.get("Brand"),
                    "desc": r.get("desc"), "price": price, "avail": r.get("avail"),
                    "kv": {k: v for k, v in o.items() if not SKIP.match(k)}})
D = ROOT / "data/ham"
json.dump(cat, open(D / "ant_catalog.json", "w"), ensure_ascii=False, indent=0)
compact.sort(key=lambda x: (x["cat"], x["slug"]))
(D / "ant_shards").mkdir(exist_ok=True)
for i in range(n):
    json.dump(compact[i::n], open(D / f"ant_shards/s{i}.json", "w"), ensure_ascii=False, indent=0)
print(f"{len(cat)} scraped, {len(compact)} priced -> {n} shards of ~{len(compact)//n}", file=sys.stderr)
