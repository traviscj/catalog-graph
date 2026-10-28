#!/usr/bin/env python3
"""Stage 1 (shelly): enumerate catalog + fetch KB spec tables.

  shopify /products.json  -> raw/p*.json
  product page            -> raw/pages/<handle>.html   (to find KB link)
  KB page                 -> raw/kb/<slug>.html
  out                     -> catalog.json  [{handle, title, family, price, kb_slug, specs:{section:{k:v}}}]

Idempotent: cached files are reused; delete to refetch.
"""
import glob, html, json, re, sys, time, urllib.request
from pathlib import Path

D = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "data/shelly")
RAW = D / "raw"
UA = {"User-Agent": "Mozilla/5.0 (catalog-graph; personal research)"}
RADIO_SUBS = {"Wi-Fi", "Bluetooth", "Zigbee", "Z-Wave", "Z-Wave LR", "LoRa", "Matter", "Thread", "Ethernet", "LAN"}
OVERRIDES = {  # family -> kb slug where name matching can't get there
    "Shelly 1-Channel Decoupler 120V": "shelly-1-channel-decoupler-120v-shelly-4-channel-decoupler-120v",
    "Shelly 4-Channel Decoupler 120V": "shelly-1-channel-decoupler-120v-shelly-4-channel-decoupler-120v",
    "Shelly Decoupler 120V": "shelly-1-channel-decoupler-120v-shelly-4-channel-decoupler-120v",
    "Shelly DALI Dimmer Gen3": "shelly-dali-dimmer-gen3-1",
    "Shelly Pro Dual Cover / Shutter PM": "shelly-pro-dual-cover-pm",
    "Shelly EM Gen3 80А": "shelly-em-gen3",
    "Shelly GAS (CNG)": "shelly-gas", "Shelly GAS (LPG)": "shelly-gas",
    "Shelly 3EM-63T Gen3": "shelly-3em-63-gen3", "Shelly 3EM-63W Gen3": "shelly-3em-63-gen3",
    "Shelly Button 1": "shelly-button-1", "Shelly Button": "shelly-button-1",
    "SSR Add-on (Shelly Pill)": "ssr-add-on",
    "Analog 0 - 30V Add-on (Shelly Pill)": "analog-0-30v-add-on",
    "Splitter 1 to 5-3.5 mm Jack（Shelly Pill)": "splitter-1-to-5-3-5mm-jack",
    "Micro USB to 5 Terminal Add（Shelly Pill)": "5-terminal-add-on",
    "Shelly Temp. Sensor DS18B20 3.5mm jack": "temperature-sensor-ds18b20-3-5mm-jack",
    "Shelly Plus i4 DC": "shelly-plus-i4dc",
    "Shelly 50A Current Transf Pro EM-50 / EM Gen3": "ct-50a",
    "FrankEver Sprinkler Controller FK-06X": "sprinkler-controller-fk-06x",
    "LightSolutions Hilux DS4": "lightsolutions-hilux-ds8-us-hilux-ds4-us",
    "LightSolutions Hilux DS8": "lightsolutions-hilux-ds8-us-hilux-ds4-us",
}
SKIP_TYPES = {"Online Course", "Accessories & Merchandise"}


def get(url, path):
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
            path.write_text(body)
            time.sleep(0.4)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                path.write_text("")
                return ""
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return ""


def products():
    out, page = [], 1
    while True:
        js = json.loads(get(f"https://us.shelly.com/products.json?limit=250&page={page}", RAW / f"p{page}.json"))
        if not js["products"]:
            return out
        out += js["products"]
        page += 1


COLOR = r"\s*[-–(]?\s*(white|black -|black|silver|grey|gray|anthracite|beige|mocha|ivory|light almond)\)?\s*$"


def family(title):
    t = re.sub(COLOR, "", title, flags=re.I)
    t = re.sub(r"\s*\((\d+[- ]pack|\d+ pcs?)\)|\s+\d+[- ]pack$|\s+(list|x\d+)$|\s*-$", "", t, flags=re.I)
    return t.strip()


def text_of(fragment):
    s = re.sub(r"<br\s*/?>", " ", fragment)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def sections(page):
    """h2 sections -> plain text (narrative: applications, safety features, load types, ...)."""
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    parts = re.split(r'<h2 id="([^"]+)"', body)
    out = {}
    for k, v in zip(parts[1::2], parts[2::2]):
        k = html.unescape(k).replace("-", " ").replace("(≠)", "").strip()
        if k in {"Specifications", "Compliance", "Printed user guide", "Installation guides", "Shelly Smart Control",
                 "Shelly Web user interface", "Components and APIs", "Downloads"}:
            continue
        t = text_of(v)
        t = t.split("Privacy policy Cookie")[0]
        if t:
            out[k] = t[:3000]
    return out


def parse_specs(page):
    """KB spec table: <tr><th colspan>Section</th></tr> ... <tr><td>Key:</td><td>Val</td></tr>.
    Sub-section rows (e.g. Radio > Wi-Fi) are single-cell rows too; we join as 'Radio/Wi-Fi'."""
    m = re.search(r'id="Specifications[^"]*"', page)
    if m:
        seg = page[m.start(): m.start() + 200_000]
        j = seg.find("</table>")
        seg = seg[: j if j > 0 else None]
    else:  # gen1-style pages: take every table in the body
        seg = "".join(re.findall(r"<table.*?</table>", page, flags=re.S))
    specs, top, sub = {}, "General", None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, flags=re.S):
        cells = [text_of(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.S)]
        cells = [c for c in cells if c]
        if not cells or cells == ["Quantity", "Value"]:
            continue
        if len(cells) == 1:
            c = cells[0]
            if c in RADIO_SUBS:
                top, sub = "Radio", c
            else:
                top, sub = c, None
            continue
        key = cells[0].rstrip(":").strip()
        val = " | ".join(cells[1:])
        sec = f"{top}/{sub}" if sub else top
        d = specs.setdefault(sec, {})
        d[key] = (d[key] + " | " + val) if key in d else val
    return specs


def toks(s):
    s = s.lower().replace("h&t", "ht").replace("ul-certified", "ul").replace("1 pm", "1pm")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\bh t\b", "ht", s)
    return {t for t in s.split() if t not in {"shelly", "the", "by", "knowledge", "base"}}


SOFT = {"list", "50a", "80а", "80a", "us", "eu", "au", "uk", "ul", "lr", "zwlr", "v1", "v2", "v3", "non", "certified", "zb"}


def match(fam, cand):
    """coverage of family tokens by candidate; 0 if candidate adds a non-soft token (e.g. 'dimmer')."""
    f, c = toks(fam), toks(cand)
    if c - f - SOFT:
        return 0.0
    bonus = 0.01 * ("us" in c) + 0.001 * max([int(t[1]) for t in c if re.fullmatch(r"v\d", t)] or [0])
    cov = len((f & c) - SOFT) / max(1, len(f - SOFT))
    return (cov + bonus) if cov == 1.0 else cov * 0.5


def versions(page):
    i = page.find('id="Versions"')
    return re.findall(r'href="/knowledge-base/([a-z0-9-]+)"', page[i:i + 5000]) if i >= 0 else []


def sim(a, b):
    a, b = toks(a), toks(b)
    return len(a & b) / max(1, len(a | b))


_SITEMAP = None


def sitemap_slugs():
    global _SITEMAP
    if _SITEMAP is None:
        xml = get("https://kb.shelly.cloud/__sitemaps/a906d70b-8e2b-4b26-a7ea-791cc5b50ea5/sitemap.xml", RAW / "kb_sitemap.xml")
        _SITEMAP = [s for s in re.findall(r"knowledge-base/([a-z0-9-]+)<", xml)
                    if not re.search(r"(guide|interface|smart-control|how-to|kbsa|copy-of|using-|-\d+$)", s)]
    return _SITEMAP


def kb_title(page):
    m = re.search(r"<title>([^<|]*)", page)
    return html.unescape(m.group(1)).strip() if m else ""


def kb_candidates(handle, page):
    links = re.findall(r"kb\.shelly\.cloud/knowledge-base/([a-z0-9-]+)", page)
    seen, out = set(), []
    for s in links:
        if s in seen or re.search(r"(guide|interface|add-new-device|-\d+$)", s):
            continue
        seen.add(s)
        out.append(s)
    # fall back to handle-derived slug
    base = re.sub(r"-(white|black|silver|grey|gray|anthracite|beige|mocha|ivory)$", "", handle)
    for s in (base, handle):
        if s not in seen:
            out.append(s)
    return out


def main():
    ps = products()
    print(f"{len(ps)} shopify products", file=sys.stderr)
    fams = {}
    for p in ps:
        if p["product_type"] in SKIP_TYPES:
            continue
        f = family(p["title"])
        fams.setdefault(f, []).append(p)
    rows = []
    for f, members in sorted(fams.items()):
        members.sort(key=lambda m: (bool(re.search(r"list|pack|-x-?\d", m["handle"])), len(m["handle"])))
        p = members[0]
        cands = []
        for m in members[:3]:
            page = get(f"https://us.shelly.com/products/{m['handle']}", RAW / "pages" / f"{m['handle']}.html")
            cands += [c for c in kb_candidates(m["handle"], page) if c not in cands]
        cands += [c for c in sitemap_slugs() if c not in cands and match(f, c) >= 0.5]
        best, seen = (0.0, None, {}, {}), set()
        if f in OVERRIDES:
            kb = get(f"https://kb.shelly.cloud/knowledge-base/{OVERRIDES[f]}", RAW / "kb" / f"{OVERRIDES[f]}.html")
            cands, best = [], (1.0, OVERRIDES[f], parse_specs(kb), sections(kb))
        while cands:
            cand = cands.pop(0)
            if cand in seen or match(f, cand) < 0.99:
                continue
            seen.add(cand)
            kb = get(f"https://kb.shelly.cloud/knowledge-base/{cand}", RAW / "kb" / f"{cand}.html")
            sp = parse_specs(kb) if kb else {}
            if not sp:
                cands += versions(kb)
                continue
            score = match(f, cand)
            if score > best[0]:
                best = (score, cand, sp, sections(kb))
        score, slug, specs, secs = best
        prices = sorted({float(v["price"]) for m in members for v in m["variants"]})
        rows.append({
            "family": f,
            "handles": [m["handle"] for m in members],
            "variants": [m["title"] for m in members],
            "product_type": p["product_type"],
            "tags": sorted({t for m in members for t in m["tags"]}),
            "price": prices[0] if prices else None,
            "price_max": prices[-1] if prices else None,
            "available": any(v.get("available") for m in members for v in m["variants"]),
            "blurb": text_of(p["body_html"] or "")[:600],
            "kb_slug": slug,
            "kb_match": round(min(score, 1.0), 2),
            "specs": specs,
            "kb_sections": secs,
        })
        print(f"{score:4.2f} {f:50s} {slug}", file=sys.stderr)
    (D / "catalog.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{len(rows)} families, {sum(1 for r in rows if r['specs'])} with specs", file=sys.stderr)


if __name__ == "__main__":
    main()
