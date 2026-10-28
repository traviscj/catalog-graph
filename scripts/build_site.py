#!/usr/bin/env python3
"""Stage 4: graph.json + catalog raw specs + pairs.json + domain SITE config -> single-file SPA.

  build_site.py data/<domain> site/<domain>.html
"""
import importlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
D, OUT = Path(sys.argv[1]), Path(sys.argv[2])
ROOT = Path(__file__).parent.parent
R = importlib.import_module(f"rules.{D.name}")
G = json.load(open(D / "graph.json"))
raw_all, acc = R.raw_index(json.load(open(D / "catalog.json")))
raw = {}
for pid, p in G["products"].items():
    r = raw_all.get(pid) or next((v for v in raw_all.values() if v.get("_name") == p["name"]), None)
    if r:
        raw[pid] = {k: v for k, v in r.items() if not k.startswith("_")}
pairs = json.load(open(D / "pairs.json")) if (D / "pairs.json").exists() else {}
jobs = {}
for line in (l for sch in [R.SITE["schema"], *R.SITE.get("schema_extra", [])] for l in open(ROOT / sch)):
    m = re.match(r"\|\s*([a-z_]+)\s*\|\s*(.*?)\s*\|$", line)
    if m and m.group(1) != "job":
        jobs[m.group(1)] = m.group(2)
# only ship accessories something actually references
used = {c for r in raw.values() for c in r.get("compat", [])} | {x["id"] for v in pairs.values() for x in v}
acc = {k: v for k, v in acc.items() if k in used}
data = {"products": G["products"], "edges": G["edges"], "pairs": pairs, "raw": raw, "jobs": jobs, "acc": acc, "config": R.SITE}
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
dom = ROOT / f"site/inv_{D.name}.js"
inv = ((ROOT / "site/inventory.js").read_text() + "\n" + dom.read_text()) if R.SITE.get("inventory") else ""
html = (ROOT / "site/template.html").read_text().replace("/*__INVENTORY__*/", inv).replace("/*__PRICING__*/", (ROOT / "site/pricing.js").read_text() if R.SITE.get("pricing") else "").replace("__TITLE__", R.SITE["title"]).replace("__DATA__", blob)
OUT.write_text(html)
print(f"{OUT}: {OUT.stat().st_size/1e3:.0f} KB, {len(data['products'])} products, {len(data['edges'])} edges, "
      f"{len(pairs)} w/ pairs, {len(acc)} accessories", file=sys.stderr)
