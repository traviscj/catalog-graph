#!/usr/bin/env python3
"""Collect per-record "pairs" (written by the normalization agents) into <domain>/pairs.json for build_site."""
import glob, json, sys
from pathlib import Path
D = Path(sys.argv[1])
out = {}
for fn in sorted(glob.glob(str(D / "features/*.json"))):
    r = json.load(open(fn))
    if r.get("pairs"):
        out[r["id"]] = r["pairs"]
json.dump(out, open(D / "pairs.json", "w"), indent=1, ensure_ascii=False)
print(f"{len(out)} records with pairs, {sum(len(v) for v in out.values())} pairs", file=sys.stderr)
