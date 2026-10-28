"""Antenna edge rules for the ham catalog (kind == "antenna"): band/power/gain/size/tuner deltas between antennas of the same mount class."""
import math
from .common import f, jobs

LOW, WARC = ["160m", "80m"], ["30m", "17m", "12m"]
GROUPS = [("160m", ["160m"], "160m"), ("80m", ["80m"], "80m"), ("60m", ["60m"], "60m"), ("40m", ["40m"], "40m"),
          ("warc", WARC, "WARC bands (30/17/12m)"), ("high", ["20m", "15m", "10m"], "20/15/10m"), ("6m", ["6m"], "6m"),
          ("2m", ["2m"], "2m"), ("70cm", ["70cm"], "70cm"), ("220", ["1.25m"], "222 MHz"), ("23cm", ["23cm"], "23cm")]
MOUNT_NEAR = {("base", "portable"), ("mobile", "portable"), ("handheld", "portable")}


def bands(r):
    return set(f(r, "ant_bands", []) or [])


def num(r, k):
    v = f(r, k)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def size(r):
    """one linear footprint number (ft): turning radius for beams, else height/length."""
    return num(r, "turn_radius_ft") or num(r, "height_ft") or num(r, "length_ft")


def deltas(a, b):
    out = []
    if a.get("legacy") and not b.get("legacy"):
        out.append(("legacy", +1, "if you want the current model"))
    ba, bb = bands(a), bands(b)
    for k, bs, label in GROUPS:
        ha, hb = any(x in ba for x in bs), any(x in bb for x in bs)
        if hb and not ha:
            out.append(("band:" + k, +1, f"if you want {label}"))
        elif ha and not hb:
            out.append(("band:" + k, -1, f"if you can skip {label}"))
    pa, pb = num(a, "max_w"), num(b, "max_w")
    if pa and pb and pb >= 2 * pa:
        out.append(("power", +1, f"if you run more power ({pb:g} W vs {pa:g} W)"))
    elif pa and pb and pa >= 2 * pb:
        out.append(("power", -1, f"if {pb:g} W is enough"))
    ga, gb = num(a, "gain_dbi"), num(b, "gain_dbi")
    if ga is not None and gb is not None and gb - ga >= 3:
        out.append(("gain", +1, f"if you want more gain (+{gb - ga:.0f} dB)"))
    elif ga is not None and gb is not None and ga - gb >= 3:
        out.append(("gain", -1, f"if {gb:g} dBi is enough"))
    if f(b, "resonant") is True and f(a, "resonant") is False:
        out.append(("tuner", +1, "if you don't want to need a tuner"))
    elif f(a, "resonant") is True and f(b, "resonant") is False:
        out.append(("tuner", -1, "if you have a tuner (wider coverage)"))
    if f(a, "radials") is True and f(b, "radials") is False:
        out.append(("radials", +1, "if you can't lay radials"))
    sa, sb = size(a), size(b)
    if sa and sb and sb <= 0.6 * sa:
        out.append(("size", +1, f"if space is tight ({sb:g} ft vs {sa:g} ft)"))
    elif sa and sb and sb >= 1.6 * sa:
        out.append(("size", -1, f"if you have room ({sb:g} ft)"))
    wa, wb = num(a, "weight_lb"), num(b, "weight_lb")
    if f(b, "mount") in ("portable", "handheld") and wa and wb and wb <= 0.5 * wa:
        out.append(("weight", +1, f"if you carry it ({wb:g} lb vs {wa:g} lb)"))
    da, db = f(a, "directional"), f(b, "directional")
    if db is True and da is False:
        out.append(("beam", +1, "if you want directivity (rotatable beam)"))
    elif da is True and db is False:
        out.append(("beam", -1, "if omnidirectional is fine (no rotator)"))
    ma, mb = f(a, "mount"), f(b, "mount")
    if ma != mb and mb:
        out.append(("mount", 0, {"base": "if it's a fixed home antenna", "mobile": "if it goes on the car",
                                 "portable": "if you set it up in the field", "handheld": "if it goes on an HT"}.get(mb, f"if you want {mb}")))
    return out


def distance(a, b, ds):
    lat = sum(1 for k, d, _ in ds if d == 0)
    pa, pb = a.get("price") or 0, b.get("price") or 0
    brand = 0 if a.get("brand") == b.get("brand") else 0.3
    return len(ds) + 0.5 * lat + brand + (0.7 if b.get("legacy") else 0) + abs(math.log((pb + 30) / (pa + 30)))


def related(a, b):
    ma, mb = f(a, "mount"), f(b, "mount")
    if ma != mb and (ma, mb) not in MOUNT_NEAR and (mb, ma) not in MOUNT_NEAR:
        return False
    ba, bb = bands(a), bands(b)
    if not (ba & bb):
        return False
    return bool(jobs(a, "primary") & jobs(b)) or bool(jobs(b, "primary") & jobs(a)) or len(ba & bb) >= 2


def point_ok(k, ds, a, b):
    if b.get("legacy") and not a.get("legacy"):
        return False
    keys = {x[0] for x in ds}
    if "mount" in keys and k not in ("mount", "size", "weight"):
        return False
    return True
