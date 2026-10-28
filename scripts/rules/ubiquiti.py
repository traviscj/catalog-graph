"""Ubiquiti UniFi edge rules: capability deltas + relatedness for build_graph."""
import math, re
from .common import f, jobs, num

MAX_DELTAS = 5
SPEED = {"100M": 0.1, "1G": 1, "1GbE": 1, "2.5G": 2.5, "2.5GbE": 2.5, "5G": 5, "5GbE": 5, "10G": 10, "10GbE": 10,
         "SFP+": 10, "25G": 25, "SFP28": 25, "40G": 40, "100G": 100, "QSFP28": 100}
WIFI = {"WiFi 5": 5, "WiFi 6": 6, "WiFi 6E": 6.5, "WiFi 7": 7}
POE_RANK = {"poe": 1, "poe+": 2, "poe++": 3, "poe_bt": 3, "poe_bt_60w": 3, "poe_bt_90w": 4}
FORM_NEED = {
    "rack_1u": "if it goes in a rack", "rack_2u": "if it goes in a rack",
    "desktop": "if it sits on a desk/shelf (no rack)", "mini": "if you want it tiny",
    "outdoor": "if it's outdoors", "in_wall": "if you want a wall-plate unit (in-wall)", "wall": "if you want it wall-mounted",
    "din": "if it mounts on DIN rail",
}
FORM_CLASS = {"rack_1u": "box", "rack_2u": "box", "desktop": "box", "rack_mountable_desktop": "box", "mini": "box", "din": "box",
              "ceiling": "ap", "wall": "ap", "in_wall": "ap", "outdoor": "ap", "pole": "ap"}


def speed(s):
    if not s:
        return None
    s = str(s)
    best = None
    for k, v in SPEED.items():
        if k.lower() in s.lower():
            best = max(best or 0, v)
    m = re.search(r"(\d+(?:\.\d+)?)\s*G", s)
    if m:
        best = max(best or 0, float(m.group(1)))
    return best


def ports(r):
    p = f(r, "ports", {}) or {}
    return {k: (v or 0) for k, v in p.items() if isinstance(v, (int, float))}


def total_ports(r):
    return sum(ports(r).values())


def poe_max(r):
    return max([POE_RANK.get(t, 0) for t in f(r, "poe_out_types", []) or []] or [0])


def ratio(a, b, k=1.5):
    return a and b and b >= k * a


NET_JOBS = ("switch", "gateway", "wifi", "console", "wireless")


def is_net(r):
    return any(j.startswith(NET_JOBS) for j in jobs(r, "primary"))


def deltas(a, b):
    out = []
    net = is_net(a) and is_net(b)
    if a.get("legacy") and not b.get("legacy"):
        out.append(("legacy", +1, "if you want the current-gen replacement"))
    elif b.get("legacy") and not a.get("legacy"):
        out.append(("legacy", -1, "(older generation)"))
    wa, wb = WIFI.get(f(a, "wifi_std")), WIFI.get(f(b, "wifi_std"))
    if wa and wb and wb > wa:
        out.append(("wifi_std", +1, f"if you want {f(b, 'wifi_std')}"))
    elif wa and wb and wb < wa:
        out.append(("wifi_std", -1, f"if {f(b, 'wifi_std')} is enough"))
    ba, bb = set(f(a, "bands", []) or []), set(f(b, "bands", []) or [])
    if ba and "6" in bb and "6" not in ba:
        out.append(("6ghz", +1, "if you want 6 GHz"))
    ca, cb = num(f(a, "max_clients")), num(f(b, "max_clients"))
    if ratio(ca, cb):
        out.append(("clients", +1, f"if you need more client capacity ({cb:g}+)"))
    elif ratio(cb, ca):
        out.append(("clients", -1, f"if {cb:g} clients is plenty"))
    pa, pb = total_ports(a), total_ports(b)
    if pa and pb and pa != pb and abs(pb - pa) >= 2:
        out.append(("ports", +1 if pb > pa else -1, f"if you need {pb} ports" if pb > pa else f"if {pb} ports is enough"))
    qa, qb = f(a, "poe_out_ports") or 0, f(b, "poe_out_ports") or 0
    if not net:
        qa = qb = 0
    if not qa and qb:
        out.append(("poe", +1, "if you need to power APs/cameras (PoE out)"))
    elif qa and not qb:
        out.append(("poe", -1, "if you don't need PoE out"))
    ja, jb = num(f(a, "poe_budget_w")), num(f(b, "poe_budget_w"))
    if qa and qb and ratio(ja, jb, 1.4):
        out.append(("poe_budget", +1, f"if you need more PoE budget ({jb:g} W)"))
    elif qa and qb and ratio(jb, ja, 1.4):
        out.append(("poe_budget", -1, f"if {jb:g} W of PoE is enough"))
    if qa and qb and poe_max(b) > poe_max(a) and poe_max(b) >= 3:
        out.append(("poe_type", +1, "if you need PoE++ (802.3bt) for big APs/PTZ"))
    ua, ub = speed(f(a, "uplink")), speed(f(b, "uplink"))
    if not net:
        ua = ub = None
    if ua and ub and ub > ua:
        out.append(("uplink", +1, f"if you need a {ub:g}G uplink"))
    elif ua and ub and ub < ua and ub >= 1:
        out.append(("uplink", -1, f"if a {ub:g}G uplink is enough"))
    sa, sb = ports(a), ports(b)
    if not sa.get("sfp_plus_10g") and sb.get("sfp_plus_10g") and not sa.get("sfp28_25g"):
        out.append(("sfp", +1, "if you need SFP+ (fiber / 10G DAC)"))
    if not sa.get("rj45_10g") and sb.get("rj45_10g"):
        out.append(("10g_rj45", +1, "if you need 10GbE copper ports"))
    if not (sa.get("rj45_2_5g") or sa.get("rj45_10g")) and sb.get("rj45_2_5g") and (sa.get("rj45_1g") or 0):
        out.append(("2_5g", +1, "if you want 2.5GbE ports (WiFi 7 APs, NAS)"))
    la, lb = f(a, "layer"), f(b, "layer")
    if la and lb and la != lb:
        rank = {"L2": 0, "L3 lite": 1, "L3": 2}
        if rank.get(lb, 0) > rank.get(la, 0):
            out.append(("layer", +1, f"if you need {lb} routing on the switch"))
    ia, ib = num(f(a, "ips_throughput_gbps")), num(f(b, "ips_throughput_gbps"))
    if ratio(ia, ib, 1.4):
        out.append(("ips", +1, f"if your internet is faster than {ia:g} Gbps (IPS on)"))
    elif ratio(ib, ia, 1.4):
        out.append(("ips", -1, f"if your internet is under {ib:g} Gbps"))
    wa_, wb_ = num(f(a, "wan_ports_max")), num(f(b, "wan_ports_max"))
    if wa_ and wb_ and wb_ > wa_:
        out.append(("wan", +1, f"if you need more WANs (up to {wb_:g})"))
    ha, hb = set(f(a, "hosts_apps", []) or []), set(f(b, "hosts_apps", []) or [])
    for app in ["protect", "access", "talk", "drive"]:
        if app in hb and app not in ha and ("network" in ha or ha):
            out.append((f"app:{app}", +1, f"if you also want to run {app.capitalize()} on it"))
    da, db = num(f(a, "max_storage_tb")), num(f(b, "max_storage_tb"))
    if ratio(da, db):
        out.append(("storage", +1, f"if you need more storage ({db:g} TB)"))
    if set(f(b, "redundancy", []) or []) - set(f(a, "redundancy", []) or []):
        out.append(("redundancy", +1, "if you need redundant PSU / HA"))
    xa, xb = set(map(str.lower, f(a, "special", []) or [])), set(map(str.lower, f(b, "special", []) or []))
    if any("wifi" in s for s in xb) and not any("wifi" in s for s in xa) and "box" == FORM_CLASS.get(f(a, "form_factor")):
        out.append(("builtin_wifi", +1, "if you want WiFi built in"))
    if any("etherlight" in s for s in xb) and not any("etherlight" in s for s in xa):
        out.append(("etherlighting", +1, "if you want Etherlighting"))
    if f(a, "requires_console") is True and f(b, "requires_console") is False:
        out.append(("console", +1, "if you don't have a UniFi console"))
    pia = max([POE_RANK.get(t, 0) for t in f(a, "power_in", []) or []] or [0])
    pib = max([POE_RANK.get(t, 0) for t in f(b, "power_in", []) or []] or [0])
    if pia and pib and pib < pia and not set(f(b, "power_in", []) or []) - set(POE_RANK):
        out.append(("power_in", +1, "if your switch can't do " + {2: "PoE+", 3: "PoE++", 4: "PoE++ 90W"}.get(pia, "PoE")))
    ra, rb = (f(a, "camera") or {}), (f(b, "camera") or {})
    if isinstance(ra, dict) and isinstance(rb, dict) and ra and rb:
        def res(c):
            s = str(c.get("res", ""))
            m = re.search(r"(\d+)\s*K", s)
            return 4 if "4K" in s else (int(m.group(1)) if m else (2 if "2K" in s or "5MP" in s else 1 if "1080" in s else None))
        xr, yr = res(ra), res(rb)
        if xr and yr and yr > xr:
            out.append(("cam_res", +1, f"if you need sharper video ({str(rb.get('res')).split(' (')[0]})"))
        if "lpr" in str(rb.get("ai", "")).lower() and "lpr" not in str(ra.get("ai", "")).lower():
            out.append(("lpr", +1, "if you need license-plate recognition"))
    fa, fb = f(a, "form_factor"), f(b, "form_factor")
    if fa != fb and fb in FORM_NEED and not ({fa, fb} <= {"rack_1u", "rack_2u"}):
        out.append(("form", 0, FORM_NEED[fb]))
    if f(b, "outdoor_rated") is True and f(a, "outdoor_rated") is not True and fb != "outdoor":
        out.append(("outdoor", +1, "if it's outdoors / needs weatherproofing"))
    return out


def distance(a, b, ds):
    lat = sum(1 for k, d, _ in ds if d == 0)
    pa, pb = a.get("price") or 0, b.get("price") or 0
    line = 0 if a.get("line") == b.get("line") else 0.5
    leg = 0.7 if b.get("legacy") else 0
    return len(ds) + 0.5 * lat + line + leg + abs(math.log((pb + 20) / (pa + 20)))


def main_job(r):
    return next((j["job"] for j in r.get("jobs", []) if j.get("role") == "primary"), None)


def related(a, b):
    ja, jb = jobs(a, "primary"), jobs(b, "primary")
    if "accessory" in ja | jb or main_job(a) not in jb or main_job(b) not in ja:
        return False
    ca, cb = FORM_CLASS.get(f(a, "form_factor")), FORM_CLASS.get(f(b, "form_factor"))
    return ca == cb or ca is None or cb is None


def point_ok(k, ds, a, b):
    keys = {kk for kk, _, _ in ds}
    # don't recommend a legacy product as the answer to a capability need
    if b.get("legacy") and not a.get("legacy"):
        return False
    # moving to a camera/AP of a different form only makes sense when the form is the point
    if "form" in keys and k not in ("form", "outdoor") and FORM_CLASS.get(f(a, "form_factor")) == "ap":
        return False
    return True


SITE = {
    "brand": "unifi/graph", "title": "UniFi Catalog Graph",
    "schema": "schema/features_ubiquiti.md",
    "legend": "ports: 1G/2.5G/10G RJ45 · S=SFP 1G · S+=SFP+ 10G · S28=SFP28 25G · Q=QSFP28 100G. PoE W = total budget.",
    "portAbbr": {"rj45_1g": "1G", "rj45_2_5g": "2.5G", "rj45_10g": "10G", "sfp_1g": "S", "sfp_plus_10g": "S+", "sfp28_25g": "S28", "qsfp28_100g": "Q"},
    "cols": [
        {"k": "line", "label": "line", "path": "line", "t": "str"},
        {"k": "form", "label": "form", "path": "f.form_factor", "t": "str"},
        {"k": "ports", "label": "ports", "path": "f.ports", "t": "ports"},
        {"k": "uplink", "label": "uplink", "path": "f.uplink", "t": "str"},
        {"k": "poeo", "label": "PoE↓", "path": "f.poe_out_ports", "t": "num"},
        {"k": "poew", "label": "PoE W", "path": "f.poe_budget_w", "t": "num"},
        {"k": "pin", "label": "power in", "path": "f.power_in", "t": "list"},
        {"k": "wifi", "label": "wifi", "path": "f.wifi_std", "t": "str"},
        {"k": "ips", "label": "IPS Gb", "path": "f.ips_throughput_gbps", "t": "num"},
        {"k": "apps", "label": "hosts", "path": "f.hosts_apps", "t": "list"},
        {"k": "cons", "label": "needs console", "path": "f.requires_console", "t": "yn"},
    ],
    "header": [
        {"label": "form", "path": "f.form_factor"}, {"label": "ports", "path": "f.ports", "t": "ports"},
        {"label": "uplink", "path": "f.uplink"}, {"label": "PoE out", "path": "f.poe_out_ports"},
        {"label": "PoE W", "path": "f.poe_budget_w"}, {"label": "power in", "path": "f.power_in", "t": "list"},
        {"label": "wifi", "path": "f.wifi_std"}, {"label": "hosts", "path": "f.hosts_apps", "t": "list"},
        {"label": "needs console", "path": "f.requires_console", "t": "yn"},
    ],
    "feats": ["form_factor", "requires_console", "hosts_apps", "managed_by", "power_in", "power_draw_w", "uplink", "ports",
              "poe_out_ports", "poe_out_types", "poe_budget_w", "layer", "wan_ports_max", "ips_throughput_gbps",
              "routing_throughput_gbps", "max_devices", "max_clients", "wifi_std", "bands", "streams", "coverage_m2",
              "outdoor_rated", "ip_rating", "storage", "max_storage_tb", "camera", "sensors", "redundancy", "special", "requires"],
    "better": {"poe_out_ports": "higher", "poe_budget_w": "higher", "ips_throughput_gbps": "higher", "routing_throughput_gbps": "higher",
               "max_devices": "higher", "max_clients": "higher", "streams": "higher", "coverage_m2": "higher", "wan_ports_max": "higher",
               "max_storage_tb": "higher", "bands": "longer", "hosts_apps": "longer", "redundancy": "longer", "ports": "ports",
               "requires_console": "false", "power_draw_w": "lower", "outdoor_rated": "true"},
}


def raw_index(catalog):
    out, acc = {}, {}
    for r in catalog:
        if not r.get("full"):
            acc[r["slug"]] = {"name": r.get("title") or r["name"], "price": r.get("price"), "sub": r["subcategory"].replace("accessories-", "")}
            continue
        links = [["techspecs", f"https://techspecs.ui.com/{r['category']}/{r['slug']}"]]
        if r.get("price"):
            links.append(["store", f"https://store.ui.com/us/en/products/{r['slug']}"])
        out[r["slug"]] = {"links": links, "specs": r.get("specs", {}), "compat": r.get("compat", [])}
    return out, acc

# inventory / planner: generic stand-ins for gear outside the catalog (third-party or discontinued).
# Each template is a product-shaped record (same `f` keys the catalog uses) so the ledger treats it identically;
# `edit` lists the spec fields a site item may override.
_P0 = {"rj45_1g": 0, "rj45_2_5g": 0, "rj45_10g": 0, "sfp_1g": 0, "sfp_plus_10g": 0}
def _tpl(id, name, job, edit, **f):
    f.setdefault("ports", dict(_P0))
    f["ports"] = {**_P0, **f["ports"]}
    return {"id": id, "name": name, "job": job, "edit": edit, "f": f}
_SW = ["ports", "uplink", "power_in"]
_POE = _SW + ["poe_out_ports", "poe_class", "poe_budget_w"]
_DEV = ["uplink", "power_in", "power_draw_w"]
SITE["inventory"] = {
    "templates": [
        _tpl("router", "Router / firewall (3rd-party)", "gateway_router", _SW, ports={"rj45_1g": 4}, uplink="1GbE", power_in=["dc"], root=True),
        _tpl("modem", "ISP modem / ONT", "upstream", [], uplink="1GbE", power_in=["ac"], upstream=True),
        _tpl("sw_unmanaged", "Unmanaged switch", "switch_edge", _SW, ports={"rj45_1g": 8}, uplink="1GbE", power_in=["dc"]),
        _tpl("sw_managed", "Managed switch (3rd-party)", "switch_edge", _SW, ports={"rj45_1g": 24}, uplink="1GbE", power_in=["ac"]),
        _tpl("sw_poe", "PoE switch (3rd-party)", "switch_poe_edge", _POE, ports={"rj45_1g": 8}, uplink="1GbE", power_in=["ac"],
             poe_out_ports=8, poe_out_types=["poe", "poe+"], poe_budget_w=65),
        _tpl("injector", "PoE injector", "accessory", ["poe_class", "poe_budget_w"], uplink=None, power_in=["ac"],
             poe_out_ports=1, poe_out_types=["poe+"], poe_budget_w=30, inline=True),
        _tpl("ap_unifi", "UniFi AP (not in catalog)", "wifi_ceiling", _DEV, uplink="1GbE", power_in=["poe"], power_draw_w=12,
             requires_console=True, managed_by="network"),
        _tpl("ap_other", "Wi-Fi AP / mesh node (3rd-party)", "wifi_ceiling", _DEV, uplink="1GbE", power_in=["ac"]),
        _tpl("cam_other", "IP camera (3rd-party PoE)", "camera_indoor", _DEV, uplink="100MbE", power_in=["poe"], power_draw_w=6),
        _tpl("server", "Server / NAS / PC", "client", _DEV, uplink="1GbE", power_in=["ac"]),
        _tpl("client", "Wired client (printer, TV, etc.)", "client", _DEV, uplink="1GbE", power_in=["ac"]),
        _tpl("selfhost", "Self-hosted UniFi Network (OS Server / VM)", "console_host", [], uplink=None, power_in=[],
             hosts_apps=["network"]),
        _tpl("need", "Capacity target (N more drops)", "need", ["uplink", "power_in", "power_draw_w"], uplink="1GbE", power_in=["ac"]),
    ],
    "apps": ["network", "protect", "access", "talk", "connect"],
}
