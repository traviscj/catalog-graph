"""Amateur transceiver edge rules (Yaesu + Icom from DX Engineering): capability deltas + relatedness for build_graph."""
import json, math, re
from .common import f, jobs, num
from . import ham_ant

MAX_DELTAS = 5
HF_BANDS = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"]
FORM_NEED = {"base": "if it's a home-shack radio", "mobile": "if it goes in the car",
             "portable": "if you want to carry it to the field (battery, light)", "handheld": "if you want it in your hand (HT)"}
# hand ↔ base comparisons are rarely the question someone is asking; keep form jumps between neighbours
FORM_NEAR = {("base", "portable"), ("base", "mobile"), ("portable", "mobile"), ("portable", "handheld"), ("mobile", "handheld")}


def bands(r):
    return set(f(r, "bands_tx", []) or [])


def pw(r, k):
    return num((f(r, "power_w") or {}).get(k))


def main_power(r):
    p = f(r, "power_w") or {}
    return num(p.get("hf")) or num(p.get("2m")) or num(p.get("70cm"))


def dv(r):
    return set(f(r, "digital_voice", []) or [])


def has(r, k):
    return f(r, k) is True


def _r_deltas(a, b):
    out = []
    if a.get("legacy") and not b.get("legacy"):
        out.append(("legacy", +1, "if you want the current model"))
    elif b.get("legacy") and not a.get("legacy"):
        out.append(("legacy", -1, "(discontinued)"))
    ba, bb = bands(a), bands(b)
    if has(b, "hf") and not has(a, "hf"):
        out.append(("hf", +1, "if you want HF (worldwide)"))
    elif has(a, "hf") and not has(b, "hf"):
        out.append(("hf", -1, "if you only need VHF/UHF"))
    if has(b, "vhf_uhf") and not has(a, "vhf_uhf"):
        out.append(("vhf_uhf", +1, "if you also want 2m/70cm"))
    elif has(a, "vhf_uhf") and not has(b, "vhf_uhf"):
        out.append(("vhf_uhf", -1, "if you don't need 2m/70cm"))
    for band, label in [("6m", "6m (magic band)"), ("4m", "4m"), ("1.25m", "222 MHz"), ("23cm", "23cm (1.2 GHz)")]:
        if band in bb and band not in ba:
            out.append((f"band:{band}", +1, f"if you want {label}"))
    if has(a, "hf") and has(b, "hf") and "160m" in ba ^ bb:
        out.append(("160m", +1 if "160m" in bb else -1, "if you want 160m" if "160m" in bb else "if you can skip 160m"))
    pa, pb = main_power(a), main_power(b)
    if pa and pb and pb >= 2 * pa:
        out.append(("power", +1, f"if you want more power ({pb:g} W vs {pa:g} W)"))
    elif pa and pb and pa >= 2 * pb:
        out.append(("power", -1, f"if {pb:g} W is enough"))
    for m in sorted(dv(b) - dv(a)):
        out.append((f"dv:{m}", +1, f"if you want {m} digital voice"))
    if dv(a) and not dv(b):
        out.append(("dv", -1, "if analog FM is enough"))
    if f(b, "band_scope") and not f(a, "band_scope"):
        out.append(("scope", +1, "if you want a band scope / waterfall"))
    elif f(a, "band_scope") and not f(b, "band_scope"):
        out.append(("scope", -1, "if you can live without a band scope"))
    for k, up, down in [
        ("dual_receive", "if you want two independent receivers (split DX, contesting)" if has(a, "hf") and has(b, "hf")
            else "if you want to monitor two frequencies at once", "if one receiver is enough"),
        ("atu", "if you want a built-in antenna tuner", "if your antenna is resonant / you have an external tuner"),
        ("usb_single_cable", "if you want one-cable USB for FT8/digital", None),
        ("lan_remote", "if you want built-in LAN/WLAN remote", None),
        ("gps", "if you want GPS built in", None),
        ("aprs", "if you want APRS / position reporting", None),
        ("full_duplex_sat", "if you want full-duplex satellite work", None),
        ("crossband_repeat", "if you want crossband repeat", None),
        ("detachable_head", "if you need a separable control head", None),
        ("rx_antenna_in", "if you want a separate receive-antenna input", None),
    ]:
        if has(b, k) and f(a, k) is False:
            out.append((k, +1, up))
        elif down and has(a, k) and f(b, k) is False:
            out.append((k, -1, down))
    if f(a, "headless") is True and f(b, "headless") is False:
        out.append(("panel", +1, "if you want a front panel (no PC/iPad needed to operate)"))
    elif f(a, "headless") is False and f(b, "headless") is True:
        out.append(("panel", -1, "if running it from a PC/iPad (SmartSDR) is fine"))
    if f(b, "ip_rating") and not f(a, "ip_rating") and f(b, "form_factor") in ("handheld", "portable"):
        ip = str(f(b, "ip_rating"))
        out.append(("waterproof", +1, f"if you need it waterproof ({ip})" if ip.endswith(("7", "8")) else f"if you want weather resistance ({ip})"))
    if f(b, "battery") and not f(a, "battery") and f(b, "form_factor") == "portable":
        out.append(("battery", +1, "if you want an internal battery"))
    fa, fb = f(a, "form_factor"), f(b, "form_factor")
    if fa != fb and fb in FORM_NEED:
        out.append(("form", 0, FORM_NEED[fb]))
    return out


def _r_distance(a, b, ds):
    lat = sum(1 for k, d, _ in ds if d == 0)
    pa, pb = a.get("price") or 0, b.get("price") or 0
    brand = 0 if a.get("brand") == b.get("brand") else 0.4
    leg = 0.7 if b.get("legacy") else 0
    leg += 0.6 if b["id"].endswith("-ob") and not a["id"].endswith("-ob") else 0   # prefer new stock as the edge target
    return len(ds) + 0.5 * lat + brand + leg + abs(math.log((pb + 50) / (pa + 50)))


def _r_related(a, b):
    ja, jb = jobs(a, "primary"), jobs(b, "primary")
    if "accessory" in ja | jb:
        return False
    fa, fb = f(a, "form_factor"), f(b, "form_factor")
    if fa != fb and (fa, fb) not in FORM_NEAR and (fb, fa) not in FORM_NEAR:
        return False
    return bool(ja & jobs(b)) or bool(jb & jobs(a))


def _r_point_ok(k, ds, a, b):
    if b.get("legacy") and not a.get("legacy"):
        return False
    keys = {x[0] for x in ds}
    # a form change only answers the form need (or a band/power need that forces it)
    if "form" in keys and k not in ("form", "hf", "vhf_uhf", "power", "battery", "waterproof", "detachable_head"):
        return False
    return True


SITE = {
    "brand": "ham/graph", "title": "Ham Transceiver Graph",
    "schema": "schema/features_ham.md",
    "legend": "Yaesu, Icom, Kenwood + FlexRadio radios listed at DX Engineering, plus Elecraft from elecraft.com. W = max RF out (HF, else 2m). DV = digital voice.",
    "cols": [
        {"k": "brand", "label": "brand", "path": "brand", "t": "str"},
        {"k": "line", "label": "line", "path": "line", "t": "str"},
        {"k": "form", "label": "form", "path": "f.form_factor", "t": "str"},
        {"k": "hf", "label": "HF", "path": "f.hf", "t": "yn"},
        {"k": "vu", "label": "V/U", "path": "f.vhf_uhf", "t": "yn"},
        {"k": "bands", "label": "bands", "path": "f.bands_tx", "t": "bands"},
        {"k": "whf", "label": "W HF", "path": "f.power_w.hf", "t": "num"},
        {"k": "w2m", "label": "W 2m", "path": "f.power_w.2m", "t": "num"},
        {"k": "dv", "label": "DV", "path": "f.digital_voice", "t": "list"},
        {"k": "rx", "label": "receiver", "path": "f.receiver_arch", "t": "str"},
        {"k": "scope", "label": "scope", "path": "f.band_scope", "t": "has"},
        {"k": "atu", "label": "ATU", "path": "f.atu", "t": "yn"},
        {"k": "usb", "label": "USB", "path": "f.usb_single_cable", "t": "yn"},
        {"k": "drx", "label": "2RX", "path": "f.dual_receive", "t": "yn"},
        {"k": "gps", "label": "GPS", "path": "f.gps", "t": "yn"},
        {"k": "ip", "label": "IP", "path": "f.ip_rating", "t": "str"},
        {"k": "kg", "label": "kg", "path": "f.weight_kg", "t": "num"},
        {"k": "pc", "label": "PC-only", "path": "f.headless", "t": "has"},
    ],
    "header": [
        {"label": "form", "path": "f.form_factor"}, {"label": "bands", "path": "f.bands_tx", "t": "list"},
        {"label": "power W", "path": "f.power_w"}, {"label": "modes", "path": "f.modes", "t": "list"},
        {"label": "receiver", "path": "f.receiver_arch"}, {"label": "scope", "path": "f.band_scope"},
        {"label": "power", "path": "f.power_source"}, {"label": "TX A", "path": "f.tx_current_a"},
    ],
    "feats": ["form_factor", "bands_tx", "hf", "vhf_uhf", "rx_range", "power_w", "modes", "digital_voice", "receiver_arch",
              "band_scope", "display", "dual_receive", "dual_watch", "atu", "usb_single_cable", "lan_remote", "wifi_bt", "gps",
              "aprs", "full_duplex_sat", "crossband_repeat", "detachable_head", "power_source", "tx_current_a", "battery",
              "ip_rating", "antenna_ports", "rx_antenna_in", "roofing_filters", "memories", "weight_kg", "size_mm", "headless", "special", "requires"],
    "better": {"bands_tx": "longer", "digital_voice": "longer", "modes": "longer", "dual_receive": "true", "dual_watch": "true",
               "atu": "true", "usb_single_cable": "true", "lan_remote": "true", "gps": "true", "aprs": "true",
               "full_duplex_sat": "true", "crossband_repeat": "true", "detachable_head": "true", "rx_antenna_in": "true", "headless": "false",
               "band_scope": "nonempty", "ip_rating": "nonempty", "antenna_ports": "higher", "memories": "higher",
               "weight_kg": "lower", "tx_current_a": "lower", "wifi_bt": "longer"},
}


def raw_index(catalog):
    out = {}
    from pathlib import Path
    ap = Path(__file__).parents[2] / "data/ham/ant_catalog.json"
    if ap.exists():
        catalog = catalog + [{**r, "specs": r.get("kv") or r.get("specs")} for r in json.load(open(ap))]
    for r in catalog:
        src = re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", r["url"]) if r.get("url") else "DX Engineering"
        out[r["slug"]] = {"links": [[src, r.get("url") or f"https://www.dxengineering.com/parts/{r['slug']}"]],
                          "specs": {src: r.get("specs") or {}}, "compat": []}
    return out, {}


# inventory: generic stand-ins for station gear outside the catalog (other brands, discontinued rigs, antennas, tuners,
# supplies). Same `f` keys as catalog radios so caps/ledger treat them identically; `edit` drives the spec editor.
_ALLB = HF_BANDS + ["6m", "4m", "2m", "1.25m", "70cm", "23cm"]
_RADIO_EDIT = [
    {"k": "form_factor", "t": "sel", "opts": ["base", "mobile", "portable", "handheld"], "l": "form"},
    {"k": "bands_tx", "t": "set", "opts": _ALLB, "l": "TX"},
    {"k": "power_w.hf", "t": "num", "l": "W HF"}, {"k": "power_w.2m", "t": "num", "l": "W 2m"}, {"k": "power_w.70cm", "t": "num", "l": "W 70cm"},
    {"k": "modes", "t": "set", "opts": ["SSB", "CW", "AM", "FM", "DATA"]},
    {"k": "digital_voice", "t": "set", "opts": ["D-STAR", "C4FM", "DMR"], "l": "DV"},
    {"k": "atu", "t": "bool", "l": "ATU"}, {"k": "usb_single_cable", "t": "bool", "l": "USB audio+CAT"}, {"k": "band_scope", "t": "bool", "l": "scope"},
    {"k": "dual_receive", "t": "bool", "l": "2 RX"}, {"k": "gps", "t": "bool", "l": "GPS"}, {"k": "aprs", "t": "bool", "l": "APRS"},
    {"k": "crossband_repeat", "t": "bool", "l": "xband"}, {"k": "detachable_head", "t": "bool", "l": "sep. head"},
    {"k": "battery", "t": "bool", "l": "int. battery"}, {"k": "ip_rating", "t": "text", "l": "IP", "w": 5},
    {"k": "power_source", "t": "sel", "opts": ["13.8 VDC external", "internal AC PSU", "internal battery + 13.8 VDC", "Li-ion pack"], "l": "power"},
    {"k": "tx_current_a", "t": "num", "l": "TX A"},
]
def _rt(id, name, job, **f):
    return {"id": id, "name": name, "job": job, "edit": _RADIO_EDIT, "f": f}
SITE["inventory"] = {
    "templates": [
        _rt("hf_rig", "HF transceiver (not in catalog)", "hf_base", form_factor="base", bands_tx=HF_BANDS + ["6m"],
            power_w={"hf": 100}, modes=["SSB", "CW", "AM", "FM", "DATA"], digital_voice=[], power_source="13.8 VDC external", tx_current_a=20),
        _rt("vu_mobile", "VHF/UHF mobile (not in catalog)", "vhf_uhf_mobile", form_factor="mobile", bands_tx=["2m", "70cm"],
            power_w={"2m": 50, "70cm": 50}, modes=["FM"], digital_voice=[], power_source="13.8 VDC external", tx_current_a=12),
        _rt("ht", "Handheld (not in catalog)", "vhf_uhf_handheld", form_factor="handheld", bands_tx=["2m", "70cm"],
            power_w={"2m": 5, "70cm": 5}, modes=["FM"], digital_voice=[], power_source="Li-ion pack", battery=True),
        {"id": "antenna", "name": "Antenna", "job": "antenna", "f": {"ant_bands": ["40m", "20m"], "resonant": True, "max_w": 100, "ant_kind": "wire"},
         "edit": [{"k": "ant_bands", "t": "set", "opts": _ALLB, "l": "bands"}, {"k": "resonant", "t": "bool", "l": "resonant (no tuner needed)"},
                  {"k": "max_w", "t": "num", "l": "max W"},
                  {"k": "ant_kind", "t": "sel", "opts": ["wire", "end-fed", "dipole", "vertical", "loop", "beam", "mobile whip", "HT whip", "dual-band vertical", "discone"], "l": "kind"}]},
        {"id": "tuner", "name": "External antenna tuner", "job": "tuner", "f": {"tuner": True, "max_w": 300, "tuner_bands": HF_BANDS + ["6m"]},
         "edit": [{"k": "max_w", "t": "num", "l": "max W"}, {"k": "tuner_bands", "t": "set", "opts": HF_BANDS + ["6m"], "l": "bands"}]},
        {"id": "psu", "name": "13.8 V power supply", "job": "power", "f": {"psu_a": 30}, "edit": [{"k": "psu_a", "t": "num", "l": "continuous A"}]},
        {"id": "digi", "name": "Digital-mode interface (Digirig, SignaLink…)", "job": "digital_iface", "f": {"digi_iface": True}, "edit": []},
        {"id": "sdr_rx", "name": "SDR receiver (RTL-SDR, Airspy…)", "job": "receiver", "f": {"rx_only": True, "hf_rx": False},
         "edit": [{"k": "hf_rx", "t": "bool", "l": "covers HF (direct sampling / upconverter)"}]},
        {"id": "other", "name": "Other station gear", "job": "other", "f": {}, "edit": []},
    ],
}


# price model (site/pricing.js): declarative feature columns for a hedonic regression of price on functionality.
# t: bool (=== true) | truthy | in (array contains v) | not (!== true) | re (regex on str) | log2 (doublings above v) | and (all of `all`)
# sign: "+" (constrained ≥ 0: a feature can't make a radio cheaper) | "±" (free: form factor, legacy, open-box)
SITE["pricing"] = {
    "scopes": [{"k": "form", "path": "f.form_factor"}, {"k": "brand", "path": "brand"}, {"k": "job", "job": True}],
    "features": [
        {"k": "hf", "l": "HF (160–10m)", "t": "bool", "path": "f.hf"},
        {"k": "6m", "l": "6m", "t": "in", "path": "f.bands_tx", "v": "6m"},
        {"k": "vu", "l": "2m/70cm", "t": "bool", "path": "f.vhf_uhf"},
        {"k": "220", "l": "222 MHz", "t": "in", "path": "f.bands_tx", "v": "1.25m"},
        {"k": "23cm", "l": "23cm", "t": "in", "path": "f.bands_tx", "v": "23cm"},
        {"k": "vussb", "l": "V/U SSB/CW (all-mode)", "t": "and", "all": [{"t": "bool", "path": "f.vhf_uhf"}, {"t": "in", "path": "f.modes", "v": "SSB"}]},
        {"k": "contest", "l": "contest-class RX (flagship)", "t": "job", "v": "hf_contest_dx"},
        {"k": "hfw", "l": "HF power, per doubling over 10 W", "t": "log2", "path": "f.power_w.hf", "v": 10},
        {"k": "vuw", "l": "V/U power, per doubling over 5 W", "t": "log2", "path": "f.power_w.2m", "v": 5},
        {"k": "dv", "l": "digital voice", "t": "truthy", "path": "f.digital_voice"},
        {"k": "dv2", "l": "2nd DV system", "t": "re", "path": "f.digital_voice", "v": ","},
        {"k": "scope", "l": "band scope", "t": "truthy", "path": "f.band_scope"},
        {"k": "2rx", "l": "2 independent RX", "t": "bool", "path": "f.dual_receive"},
        {"k": "atu", "l": "internal ATU", "t": "bool", "path": "f.atu"},
        {"k": "usb", "l": "1-cable USB digi", "t": "bool", "path": "f.usb_single_cable"},
        {"k": "lan", "l": "LAN remote", "t": "bool", "path": "f.lan_remote"},
        {"k": "gps", "l": "GPS", "t": "bool", "path": "f.gps"},
        {"k": "aprs", "l": "APRS", "t": "bool", "path": "f.aprs"},
        {"k": "sat", "l": "full-duplex sat", "t": "bool", "path": "f.full_duplex_sat"},
        {"k": "xband", "l": "crossband repeat", "t": "bool", "path": "f.crossband_repeat"},
        {"k": "head", "l": "separable head", "t": "bool", "path": "f.detachable_head"},
        {"k": "rxant", "l": "RX antenna input", "t": "bool", "path": "f.rx_antenna_in"},
        {"k": "wx", "l": "waterproof (IPx7/8)", "t": "re", "path": "f.ip_rating", "v": "[78]$"},
        {"k": "acpsu", "l": "internal AC supply", "t": "re", "path": "f.power_source", "v": "internal AC"},
        {"k": "batt", "l": "internal battery (portable)", "t": "and", "all": [{"t": "truthy", "path": "f.battery"}, {"t": "re", "path": "f.form_factor", "v": "portable"}]},
        {"k": "pconly", "l": "PC-only (no front panel)", "t": "bool", "path": "f.headless", "sign": "±"},
        {"k": "f_hand", "l": "form: handheld", "t": "re", "path": "f.form_factor", "v": "^handheld$", "sign": "±"},
        {"k": "f_mob", "l": "form: mobile", "t": "re", "path": "f.form_factor", "v": "^mobile$", "sign": "±"},
        {"k": "f_port", "l": "form: portable", "t": "re", "path": "f.form_factor", "v": "^portable$", "sign": "±"},
        {"k": "legacy", "l": "legacy / superseded", "t": "bool", "path": "legacy", "sign": "±"},
        {"k": "ob", "l": "open box", "t": "re", "path": "id", "v": "-ob$", "sign": "±"},
    ],
}


# kind dispatch: radios and antennas never connect; each kind has its own delta rules
def _kind(r):
    return r.get("kind") or "radio"


def deltas(a, b):
    return ham_ant.deltas(a, b) if _kind(a) == "antenna" else _r_deltas(a, b)


def distance(a, b, ds):
    return ham_ant.distance(a, b, ds) if _kind(a) == "antenna" else _r_distance(a, b, ds)


def related(a, b):
    if _kind(a) != _kind(b):
        return False
    return ham_ant.related(a, b) if _kind(a) == "antenna" else _r_related(a, b)


def point_ok(k, ds, a, b):
    return ham_ant.point_ok(k, ds, a, b) if _kind(a) == "antenna" else _r_point_ok(k, ds, a, b)


# antennas live in the same catalog (kind == "antenna") so station inventory can hold catalog antennas directly
SITE["schema_extra"] = ["schema/features_ham_ant.md"]
SITE["kinds"] = {
    "radio": {"label": "radios", "cols": SITE["cols"], "header": SITE["header"], "feats": SITE["feats"], "better": SITE["better"], "legend": SITE["legend"]},
    "antenna": {
        "label": "antennas",
        "legend": "Antennas listed at DX Engineering (HF wire/vertical/beam/portable/mobile, VHF/UHF base/beam/mobile, HT). Bands = ham bands covered as sold; tuner = needs a tuner on those bands.",
        "cols": [
            {"k": "brand", "label": "brand", "path": "brand", "t": "str"},
            {"k": "line", "label": "line", "path": "line", "t": "str"},
            {"k": "mount", "label": "mount", "path": "f.mount", "t": "str"},
            {"k": "abands", "label": "bands", "path": "f.ant_bands", "t": "bands"},
            {"k": "nb", "label": "#b", "path": "f.ant_bands", "t": "count"},
            {"k": "w", "label": "W PEP", "path": "f.max_w", "t": "num"},
            {"k": "tuner", "label": "tuner?", "path": "f.resonant", "t": "tuner"},
            {"k": "gain", "label": "dBi", "path": "f.gain_dbi", "t": "num"},
            {"k": "el", "label": "el", "path": "f.elements", "t": "num"},
            {"k": "size", "label": "len/ht ft", "path": "f.length_ft", "t": "num"},
            {"k": "hgt", "label": "ht ft", "path": "f.height_ft", "t": "num"},
            {"k": "tr", "label": "turn ft", "path": "f.turn_radius_ft", "t": "num"},
            {"k": "lb", "label": "lb", "path": "f.weight_lb", "t": "num"},
            {"k": "rad", "label": "radials", "path": "f.radials", "t": "has"},
            {"k": "rx", "label": "RX only", "path": "f.rx_only", "t": "has"},
        ],
        "header": [{"label": "type", "path": "f.ant_type"}, {"label": "mount", "path": "f.mount"}, {"label": "bands", "path": "f.ant_bands", "t": "list"},
                   {"label": "max W", "path": "f.max_w"}, {"label": "resonant", "path": "f.resonant"}, {"label": "gain dBi", "path": "f.gain_dbi"},
                   {"label": "polarization", "path": "f.polarization"}],
        "feats": ["ant_type", "mount", "ant_bands", "resonant", "tuner_req", "max_w", "max_w_digital", "gain_dbi", "elements", "boom_ft",
                  "turn_radius_ft", "wind_sqft", "length_ft", "height_ft", "weight_lb", "radials", "directional", "polarization", "connector",
                  "rx_only", "assembled"],
        "better": {"ant_bands": "longer", "max_w": "higher", "max_w_digital": "higher", "gain_dbi": "higher", "resonant": "true",
                   "radials": "false", "weight_lb": "lower", "turn_radius_ft": "lower", "wind_sqft": "lower"},
    },
}
SITE["pricing"]["scopes"].insert(0, {"k": "kind", "path": "kind", "default": "radio"})
SITE["pricing"]["scopes"].insert(2, {"k": "mount", "path": "f.mount"})
for _d in SITE["pricing"]["features"]:
    _d.setdefault("kind", "radio")
_AB = lambda b: {"t": "in", "path": "f.ant_bands", "v": b, "kind": "antenna"}
SITE["pricing"]["features"] += [
    {"k": "a160", "l": "160m", **_AB("160m")}, {"k": "a80", "l": "80m", **_AB("80m")}, {"k": "a60", "l": "60m", **_AB("60m")},
    {"k": "a40", "l": "40m", **_AB("40m")}, {"k": "a30", "l": "30m", **_AB("30m")}, {"k": "a20", "l": "20m", **_AB("20m")},
    {"k": "a17", "l": "17m", **_AB("17m")}, {"k": "a15", "l": "15m", **_AB("15m")}, {"k": "a12", "l": "12m", **_AB("12m")},
    {"k": "a10", "l": "10m", **_AB("10m")}, {"k": "a6", "l": "6m", **_AB("6m")}, {"k": "a2", "l": "2m", **_AB("2m")},
    {"k": "a220", "l": "222 MHz", **_AB("1.25m")}, {"k": "a70", "l": "70cm", **_AB("70cm")}, {"k": "a23", "l": "23cm", **_AB("23cm")},
    {"k": "apw", "l": "power rating, per doubling over 100 W", "t": "log2", "path": "f.max_w", "v": 100, "kind": "antenna"},
    {"k": "again", "l": "gain, per dBi over 0", "t": "lin", "path": "f.gain_dbi", "kind": "antenna"},
    {"k": "ael", "l": "beam elements, each", "t": "lin", "path": "f.elements", "kind": "antenna"},
    {"k": "aboom", "l": "boom length, per ft", "t": "lin", "path": "f.boom_ft", "kind": "antenna"},
    {"k": "ares", "l": "resonant (no tuner needed)", "t": "bool", "path": "f.resonant", "kind": "antenna"},
    {"k": "adir", "l": "directional (beam)", "t": "bool", "path": "f.directional", "kind": "antenna", "sign": "±"},
    {"k": "arad", "l": "needs radials", "t": "bool", "path": "f.radials", "kind": "antenna", "sign": "±"},
    {"k": "arx", "l": "receive-only", "t": "bool", "path": "f.rx_only", "kind": "antenna", "sign": "±"},
    {"k": "am_port", "l": "mount: portable", "t": "re", "path": "f.mount", "v": "^portable$", "kind": "antenna", "sign": "±"},
    {"k": "am_mob", "l": "mount: mobile", "t": "re", "path": "f.mount", "v": "^mobile$", "kind": "antenna", "sign": "±"},
    {"k": "am_ht", "l": "mount: handheld", "t": "re", "path": "f.mount", "v": "^handheld$", "kind": "antenna", "sign": "±"},
    {"k": "akit", "l": "kit (not assembled)", "t": "bool", "path": "f.assembled", "neg": True, "kind": "antenna", "sign": "±"},
]


def CAP(r):
    return 10 if _kind(r) == "antenna" else 10**6

# eHam owner ratings (scripts/eham_join.py): column for both kinds + a free-signed quality term in the price model
for _k in ("radio", "antenna"):
    SITE["kinds"][_k]["cols"] = SITE["kinds"][_k]["cols"] + [{"k": "eham", "label": "eHam", "path": "rating", "t": "rating"}]
    SITE["pricing"]["features"].append({"k": "q_" + _k, "l": "eHam rating, per point vs 4.3 (shrunk by #reviews)", "t": "rating", "path": "rating",
                                        "v": 4.3, "kind": _k, "sign": "±"})
