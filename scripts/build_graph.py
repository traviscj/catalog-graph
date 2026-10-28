#!/usr/bin/env python3
"""Stage 3: feature records -> typed edge graph (domain rules in rules/<domain>.py).

For each product A and each *capability delta* d (e.g. +metering, +PoE budget, legacy->current),
find the nearest product B that realizes d while changing the least else. Emit
  {src, dst, kind: upgrade|downgrade|sidegrade, need: "if you need power monitoring", deltas:[...], dprice}
Rule module must define: deltas(a,b)->[(key, dir, label)], distance(a,b,ds), related(a,b), point_ok(k,ds,a,b).

  build_graph.py data/shelly  -> data/shelly/graph.json
"""
import glob, importlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
D = Path(sys.argv[1])
R = importlib.import_module(f"rules.{D.name}")
P = {}
for fn in sorted(glob.glob(str(D / "features/*.json"))):
    r = json.load(open(fn))
    P[r["id"]] = r
MAX_DELTAS = getattr(R, "MAX_DELTAS", 4)

edges, diffs = [], []
ids = sorted(P)
for x in ids:
    a = P[x]
    best = {}  # need-label -> (dist, y, ds)
    for y in ids:
        if x == y or not R.related(a, P[y]):
            continue
        b = P[y]
        ds = R.deltas(a, b)
        if not ds:
            continue
        dist = R.distance(a, b, ds)
        for k, d, need in ds:
            # only label edges where this delta is the *point*; ignore if >3 other things change
            if len(ds) > MAX_DELTAS or not R.point_ok(k, ds, a, b):
                continue
            cur = best.get(need)
            if cur is None or dist < cur[0]:
                best[need] = (dist, y, ds)
    for need, (dist, y, ds) in best.items():
        gains = sum(1 for _, d, _ in ds if d > 0)
        losses = sum(1 for _, d, _ in ds if d < 0)
        kind = "upgrade" if gains and not losses else "downgrade" if losses and not gains else "sidegrade"
        dprice = round((P[y].get("price") or 0) - (a.get("price") or 0), 2)
        edges.append({"src": x, "dst": y, "need": need, "kind": kind, "dprice": dprice,
                      "deltas": [{"k": k, "d": d, "label": l} for k, d, l in ds], "dist": round(dist, 2)})

# optional per-source cap (rule module CAP(product) -> max edges): big catalogs keep each source's nearest edges only
if hasattr(R, "CAP"):
    by = {}
    for e in edges:
        by.setdefault(e["src"], []).append(e)
    edges = [e for src, es in by.items() for e in sorted(es, key=lambda e: e["dist"])[:R.CAP(P[src])]]
seen = set()
for e in edges:
    k = tuple(sorted((e["src"], e["dst"])))
    if k not in seen:
        seen.add(k)
        diffs.append(list(k))

json.dump({"products": P, "edges": edges, "diffs": diffs}, open(D / "graph.json", "w"), indent=1, ensure_ascii=False)
print(f"{len(P)} products, {len(edges)} edges, {len(diffs)} diff pairs", file=sys.stderr)
