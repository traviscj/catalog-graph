#!/usr/bin/env python3
"""Stage 1 (ubiquiti): techspecs.ui.com (structured specs, Next.js __NEXT_DATA__) + store.ui.com (prices).

  techspecs category pages -> product list (slug, uuid, subcategory, tags)
  techspecs product pages  -> technicalSpecification sections (flattened "Parent › Label": value)
                              + referencedCompatibleProductIds (free "works with" edges)
  store category pages     -> USD price by slug / sku
  out: catalog.json  [{slug, id, name, title, category, subcategory, price, desc, tags, specs, compat, full}]

Accessories are fetched as lightweight nodes (no product page) unless FULL_ACCESSORY_SUBCATS.
"""
import json, re, sys, time, urllib.request
from pathlib import Path

D = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "data/ubiquiti")
RAW = D / "raw"
UA = {"User-Agent": "Mozilla/5.0 (catalog-graph; personal research)"}
FULL_CATS = ["unifi/cloud-gateways", "unifi/switching", "unifi/wifi", "unifi/physical-security",
             "unifi/door-access", "unifi/integrations"]
LIGHT_CATS = ["unifi/accessories"]
SKIP_SUBCATS = {"physical-security-accessories", "door-access-accessories"}  # duplicated under unifi/accessories
STORE_CATS = ["all-cloud-gateways", "all-switching", "all-wifi", "all-physical-security", "all-door-access",
              "all-integrations", "all-accessories", "accessories-cables-dacs", "accessories-modules-fiber",
              "accessories-poe-power", "accessories-rack-mount", "accessories-storage", "accessories-access-point",
              "accessories-camera", "accessories-door-access", "accessories-installations", "accessories-advanced-hosting"]


def get(url, path):
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                body = r.read().decode("utf-8", "replace")
            path.write_text(body)
            time.sleep(0.3)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                path.write_text("")
                return ""
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return ""


def next_data(page):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else {}


def flatten_specs(ts):
    out = {}
    for sec in (ts or {}).get("sections", []):
        sname = (sec.get("section") or {}).get("label", "?")
        labels = {f["feature"]["id"]: f["feature"]["label"] for f in sec["features"]}
        d = {}
        for f in sec["features"]:
            feat = f["feature"]
            if "value" in f:
                v = (f.get("value") or "").replace("\n", " ").strip()
            elif "flag" in f:
                v = {"True": "yes", "False": "no"}.get(f.get("flag"), f.get("flag"))
            else:
                continue  # group header
            if f.get("note"):
                v += f"  [{f['note'].strip()}]"
            k = feat["label"]
            if feat.get("parentId") in labels:
                k = f"{labels[feat['parentId']]} › {k}"
            d[k] = v
        if d:
            out[sname] = d
    return out


def store_prices():
    by = {}
    for c in STORE_CATS:
        nd = next_data(get(f"https://store.ui.com/us/en/category/{c}", RAW / "store" / f"{c}.html"))

        def walk(o):
            if isinstance(o, dict):
                if "variants" in o and "slug" in o and isinstance(o["variants"], list):
                    prices = [v["displayPrice"]["amount"] / 100 for v in o["variants"]
                              if isinstance(v, dict) and v.get("displayPrice")]
                    if prices:
                        rec = {"price": min(prices), "store_slug": o["slug"],
                               "status": next((v.get("status") for v in o["variants"] if isinstance(v, dict)), None)}
                        by.setdefault(o["slug"], rec)
                        for v in o["variants"]:
                            if isinstance(v, dict):
                                for k in ("sku", "displaySku", "defaultSku"):
                                    if v.get(k):
                                        by.setdefault(v[k].lower(), rec)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(nd)
    return by


def main():
    prices = store_prices()
    print(f"{len(prices)} store price keys", file=sys.stderr)
    rows, seen = [], set()
    for cat, full in [(c, True) for c in FULL_CATS] + [(c, False) for c in LIGHT_CATS]:
        nd = next_data(get(f"https://techspecs.ui.com/{cat}", RAW / "cat" / f"{cat.replace('/', '_')}.html"))
        for sc in nd["props"]["pageProps"]["subCategoriesWithProducts"]:
            if sc["id"] in SKIP_SUBCATS:
                continue
            for p in sc["products"]:
                if p["slug"] in seen:
                    continue
                seen.add(p["slug"])
                tags = [t["name"] for t in p.get("tags", [])]
                row = {"slug": p["slug"], "id": p["id"], "name": p["name"], "title": p.get("shortTitle"),
                       "category": cat, "subcategory": sc["id"], "full": full,
                       "tags": [t for t in tags if t.startswith("feature:") or t.endswith("-capacity")]}
                pr = prices.get(p["slug"]) or prices.get(p["name"].lower()) or prices.get(f"{p['slug']}-us")
                row["price"] = pr["price"] if pr else None
                row["status"] = pr["status"] if pr else None
                if full:
                    page = get(f"https://techspecs.ui.com/{cat}/{p['slug']}", RAW / "prod" / f"{p['slug']}.html")
                    prod = (next_data(page).get("props", {}).get("pageProps", {}) or {}).get("product") or {}
                    row["title"] = prod.get("title") or row["title"]
                    row["desc"] = prod.get("shortDescription")
                    row["skus"] = [v.get("sku") for v in prod.get("variants", []) if v.get("sku")]
                    row["specs"] = flatten_specs(prod.get("technicalSpecification"))
                    row["compat_ids"] = prod.get("referencedCompatibleProductIds") or []
                    if row["price"] is None:
                        for s in row["skus"]:
                            pr = prices.get(s.lower())
                            if pr:
                                row["price"], row["status"] = pr["price"], pr["status"]
                                break
                rows.append(row)
    uuid2slug = {r["id"]: r["slug"] for r in rows}
    for r in rows:
        r["compat"] = sorted({uuid2slug[i] for i in r.pop("compat_ids", []) if i in uuid2slug})
    (D / "catalog.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    full = [r for r in rows if r["full"]]
    print(f"{len(rows)} products ({len(full)} full), {sum(1 for r in full if r['specs'])} w/ specs, "
          f"{sum(1 for r in rows if r['price'])} priced, {sum(len(r['compat']) for r in rows)} compat edges", file=sys.stderr)


if __name__ == "__main__":
    main()
