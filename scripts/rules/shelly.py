"""Shelly edge rules: capability deltas + relatedness for build_graph."""
import math
from .common import f, jobs, num

MET = {"none": 0, None: 0, "per_channel": 2, "whole_circuit": 1, "1ph_clamp": 1, "2ch_clamp": 2, "3ph_clamp": 3}
RADIO_NEED = {
    "zwave": "if you're on a Z-Wave hub (no Wi-Fi on your IoT)",
    "zwave_lr": "if you need Z-Wave Long Range",
    "ethernet": "if you want wired Ethernet (no Wi-Fi dependency)",
    "zigbee": "if you run Zigbee",
    "matter_over_wifi": "if you want Matter",
    "lora": "if you need km-range LoRa",
    "wifi": "if you want plain Wi-Fi (no hub/controller)",
}
FORM_NEED = {
    "din_rail": "if it lives in the breaker panel (DIN rail)",
    "in_wall_mini": "if the box is tight (smaller)",
    "in_wall": "if you want it behind the switch, in the wall box",
    "plug": "if you won't touch wiring (plug-in)",
    "wall_device": "if you want a wall-mounted switch/dimmer face",
    "battery_sensor": "if there's no power where it goes (battery)",
}


def deltas(a, b):
    """list of (key, direction, need-label) describing what b changes relative to a.
    direction: +1 gain, -1 loss, 0 lateral."""
    out = []
    ma, mb = MET.get(f(a, "power_metering"), 0), MET.get(f(b, "power_metering"), 0)
    if mb > ma:
        out.append(("metering", +1, "if you need power monitoring" if ma == 0 else "if you need per-channel / more metering"))
    elif mb < ma:
        out.append(("metering", -1, "if you don't need power monitoring"))
    ca, cb = f(a, "channels"), f(b, "channels")
    if isinstance(ca, (int, float)) and isinstance(cb, (int, float)) and ca != cb and ca > 0 and cb > 0:
        out.append(("channels", +1 if cb > ca else -1, f"if you need {int(cb)} channels" if cb > ca else f"if {int(cb)} channel{'s' if cb > 1 else ''} is enough"))
    ia, ib = num(f(a, "max_current_a")), num(f(b, "max_current_a"))
    if ia and ib and abs(ib - ia) >= 2:
        out.append(("amps", +1 if ib > ia else -1, f"if your load is over {ia:g}A (up to {ib:g}A)" if ib > ia else f"if your load stays under {ib:g}A"))
    da, db = f(a, "dimming"), f(b, "dimming")
    if db and not da:
        out.append(("dimming", +1, f"if you need to dim ({db})"))
    elif da and not db:
        out.append(("dimming", -1, "if you only need on/off"))
    elif da and db and da != db:
        out.append(("dimming", 0, f"if your driver is {db}, not {da}"))
    if f(b, "cover_control") is True and f(a, "cover_control") is not True:
        out.append(("cover", +1, "if you're driving a shutter/blind motor"))
    if f(b, "color_light") and not f(a, "color_light"):
        out.append(("color", +1, f"if you need color ({f(b, 'color_light')})"))
    na, nb = f(a, "neutral_required"), f(b, "neutral_required")
    if na is True and nb is False:
        out.append(("neutral", +1, "if your box has no neutral"))
    elif na is False and nb is True:
        out.append(("neutral", -1, "if you do have a neutral"))
    ra, rb = set(f(a, "radios", [])), set(f(b, "radios", []))
    for r in sorted(rb - ra):
        if r in RADIO_NEED:
            out.append((f"radio:{r}", 0, RADIO_NEED[r]))
    if "wifi" in ra and "wifi" not in rb and ("zwave" in rb or "zwave_lr" in rb):
        pass  # already captured by zwave entry
    fa, fb = f(a, "form_factor"), f(b, "form_factor")
    if fa != fb and fb in FORM_NEED and not (fa == "in_wall_mini" and fb == "in_wall"):
        out.append(("form", 0, FORM_NEED[fb]))
    if f(b, "ul_listed") is True and f(a, "ul_listed") is not True:
        out.append(("ul", +1, "if you need UL listing (inspector/insurer)"))
    elif f(a, "ul_listed") is True and f(b, "ul_listed") is False:
        out.append(("ul", -1, "if you don't need UL listing"))
    pa, pb = set(f(a, "protections", [])), set(f(b, "protections", []))
    if len(pb - pa) >= 2:
        out.append(("protections", +1, "if you want over-V/I/power cutoffs"))
    if f(b, "dc_supply") is True and f(a, "dc_supply") is not True:
        out.append(("dc", +1, "if you only have 12/24V DC"))
    if f(b, "addon_port") is True and f(a, "addon_port") is not True:
        out.append(("addon", +1, "if you want to add temp probes / sensor add-on"))
    return out


def distance(a, b, ds):
    """how much else changes besides the labeled deltas — for picking the nearest realizer."""
    lat = sum(1 for k, d, _ in ds if d == 0)
    pa, pb = a.get("price") or 0, b.get("price") or 0
    line = 0 if a.get("line") == b.get("line") else 0.5
    return len(ds) + 0.5 * lat + line + abs(math.log((pb + 5) / (pa + 5)))


FORM_CLASS = {"in_wall": "ctl", "in_wall_mini": "ctl", "din_rail": "ctl", "wall_device": "ctl", "plug": "ctl",
              "bulb": "bulb", "battery_sensor": "sensor", "wired_sensor": "sensor", "addon": "addon",
              "accessory": "acc", "clamp_ct": "acc", "hub_display": "hub", "camera": "cam"}


def ecosystem(r):
    rs = set(f(r, "radios", []))
    if rs & {"zwave", "zwave_lr"} and not rs & {"wifi", "ethernet"}:
        return "zwave"
    if rs <= {"bluetooth", "zigbee"} and rs:
        return "ble"
    return "ip"


def related(a, b):
    ja, jb = jobs(a, "primary"), jobs(b, "primary")
    if not (ja & jb) or "accessory" in ja | jb:
        return False
    return FORM_CLASS.get(f(a, "form_factor"), "x") == FORM_CLASS.get(f(b, "form_factor"), "y")


FUNC = {"dimming", "cover", "color"}


def point_ok(k, ds, a, b):
    """is delta k a legitimate *reason* for the a->b move? reject if b also changes function or ecosystem
    and k isn't that change."""
    keys = {kk for kk, _, _ in ds}
    if (keys & FUNC) and k not in FUNC:
        return False
    if ecosystem(a) != ecosystem(b) and not k.startswith("radio:"):
        return False
    if (f(a, "form_factor") == "plug") != (f(b, "form_factor") == "plug") and k != "form":
        return False
    if "dimming" in keys and k != "dimming" and k != "form":
        return False
    return True


SITE = {
    "brand": "shelly/graph", "title": "Shelly Catalog Graph",
    "schema": "schema/features.md",
    "legend": "radios: W wifi · E ethernet · B bluetooth · Zb zigbee · ZW z-wave · LR z-wave LR · Lo LoRa · M matter.",
    "cols": [
        {"k": "line", "label": "line", "path": "line", "t": "str"},
        {"k": "form", "label": "form", "path": "f.form_factor", "t": "str"},
        {"k": "ch", "label": "ch", "path": "f.channels", "t": "num"},
        {"k": "amps", "label": "A/ch", "path": "f.max_current_a", "t": "num"},
        {"k": "meter", "label": "meter", "path": "f.power_metering", "t": "pos",
         "map": {"per_channel": "per-ch", "whole_circuit": "total", "1ph_clamp": "1φ CT", "2ch_clamp": "2× CT", "3ph_clamp": "3φ CT"}},
        {"k": "dim", "label": "dim", "path": "f.dimming", "t": "str"},
        {"k": "neutral", "label": "N req", "path": "f.neutral_required", "t": "yn"},
        {"k": "radio", "label": "radios", "path": "f.radios", "t": "abbr",
         "map": {"wifi": "W", "ethernet": "E", "bluetooth": "B", "zigbee": "Zb", "zwave": "ZW", "zwave_lr": "LR", "lora": "Lo", "matter_over_wifi": "M", "thread": "T"}},
        {"k": "ul", "label": "UL", "path": "f.ul_listed", "t": "yn"},
    ],
    "header": [
        {"label": "form", "path": "f.form_factor"}, {"label": "ch", "path": "f.channels"},
        {"label": "A/ch", "path": "f.max_current_a"}, {"label": "meter", "path": "f.power_metering"},
        {"label": "N req", "path": "f.neutral_required", "t": "yn"}, {"label": "UL", "path": "f.ul_listed", "t": "yn"},
        {"label": "radios", "path": "f.radios", "t": "list"},
    ],
    "feats": ['form_factor', 'supply', 'mains_powered', 'dc_supply', 'battery', 'neutral_required', 'channels', 'output_type',
              'max_current_a', 'max_power_w', 'dc_switching', 'power_metering', 'metering_max_a', 'dimming', 'cover_control',
              'color_light', 'inputs', 'input_count', 'sensors', 'radios', 'matter', 'ble_gateway', 'zwave_repeater', 'local_api',
              'mqtt', 'scripting', 'ul_listed', 'protections', 'addon_port', 'temp_range_c', 'size_mm', 'requires'],
    "better": {"max_current_a": "higher", "max_power_w": "higher", "channels": "higher", "input_count": "higher",
               "power_metering": "nonempty", "neutral_required": "false", "ul_listed": "true", "protections": "longer",
               "radios": "longer", "local_api": "true", "mqtt": "true", "scripting": "true", "addon_port": "true"},
}


def raw_index(catalog):
    """catalog.json rows -> {product_id: {links, specs, compat}}, accessories {}"""
    import re
    out = {}
    for r in catalog:
        pid = re.sub(r"[^a-z0-9]+", "-", r["family"].lower()).strip("-")
        links = []
        if r.get("kb_slug"):
            links.append(["kb", f"https://kb.shelly.cloud/knowledge-base/{r['kb_slug']}"])
        if r.get("handles"):
            links.append(["shop", f"https://us.shelly.com/products/{r['handles'][0]}"])
        out[pid] = {"links": links, "specs": r.get("specs", {}), "_name": r["family"]}
    return out, {}
