#!/usr/bin/env python3
"""Manufacturer Shopify feeds (data/ham/raw/shopify/<domain>_<page>.json) -> antenna candidates in the DXE compact-shard shape.

Appends to data/ham/ant_catalog.json (source/url set) and writes data/ham/ant_shards/x<i>.json for normalization.
Skips products whose model token already exists among DXE antennas (DXE record wins; same item, same-ish price).
"""
import glob, html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
D = ROOT / "data/ham"
SRC = {
    "mfjenterprises.com": ("mfj", lambda p: p["product_type"] == "Antenna"),
    "chameleonantenna.com": ("chd", lambda p: p["product_type"] in ("Antenna Systems", "Wire Antennas") or re.search(r"\bF-?LOOP|SKYLOOP", p["title"], re.I)),
    "tufteln.com": ("tuf", lambda p: re.search(r"antenna|efhw|efrw|dipole|loop|vertical|reel", p["title"], re.I)
                    and not re.search(r"used|mount|clamp|strap|adapt|stand|transformer|link kit", p["title"], re.I)),
}


def txt(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h or "", flags=re.S)
    h = re.sub(r"<(br|p|li|tr|h\d|div)[^>]*>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h))
    return re.sub(r"[ \t\xa0]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


tok = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
dxe = [r for r in json.load(open(D / "ant_catalog.json")) if not r.get("url")]
# model tokens: alnum runs containing a digit, from DXE names and slugs (slug minus its 3-letter brand prefix), hyphens split and joined
def toks(s):
    ws = [w for w in re.split(r"[^A-Za-z0-9]+", s) if w]
    model = lambda w: (re.search(r"\d", w) and re.search(r"[A-Za-z]", w) and len(w) >= 3) or (w.isdigit() and len(w) >= 3)
    return {tok(w) for w in ws if model(w)} | {tok(a + b) for a, b in zip(ws, ws[1:]) if model(a + b) and not (a.isdigit() and b.isdigit())}
dxe_tokens = set().union(*(toks((r.get("name") or "") + " " + r["slug"][4:]) for r in dxe))
out, dup = [], 0
for dom, (pre, keep) in SRC.items():
    for fn in sorted(glob.glob(str(D / f"raw/shopify/{dom}_*.json"))):
        for p in json.load(open(fn)).get("products", []):
            if not keep(p):
                continue
            v = next((v for v in p["variants"] if v.get("available")), p["variants"][0])
            price = float(v["price"] or 0)
            if not price:
                continue
            model = re.sub(r"^(CHA|MFJ)\s+", "", p["title"]).split(",")[0].strip()
            mt = toks(model.split(" (")[0])
            if mt and mt & dxe_tokens and dom != "tufteln.com":
                dup += 1
                continue
            out.append({"slug": f"{pre}-{p['handle']}"[:60], "cat": f"{dom}/{p['product_type'] or '-'}", "name": p["title"], "brand": p["vendor"],
                        "desc": p["title"], "price": price, "list": v.get("compare_at_price"), "avail": "InStock" if v.get("available") else "Unknown",
                        "specs": {}, "kv": {}, "ov": txt(p.get("body_html"))[:2500], "url": f"https://{dom}/products/{p['handle']}"})
cat = [r for r in json.load(open(D / "ant_catalog.json")) if not r.get("url")] + out
json.dump(cat, open(D / "ant_catalog.json", "w"), ensure_ascii=False, indent=0)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
compact = [{k: r[k] for k in ("slug", "cat", "name", "brand", "desc", "price", "avail", "kv")} | {"text": r["ov"]} for r in out]
for i in range(n):
    json.dump(compact[i::n], open(D / f"ant_shards/x{i}.json", "w"), ensure_ascii=False, indent=0)
print(f"{len(out)} new manufacturer antennas ({dup} skipped as DXE duplicates) -> {n} shards", file=sys.stderr)
