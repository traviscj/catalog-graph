# Normalized product record — Ubiquiti UniFi (stage 2 output), one JSON per product

Same envelope as Shelly. Unknown → null (not false). Ground everything in specs/desc/tags.

```jsonc
{
  "id": "u7-pro",                      // = techspecs slug, verbatim
  "name": "U7 Pro",                    // product name/SKU as Ubiquiti writes it
  "title": "U7 Pro",                   // human title
  "price": 189.0,                      // null if not in store
  "line": "WiFi 7",                    // short family label: e.g. "Cloud Gateway", "Pro Max switch", "Ultra switch", "Lite switch", "Flex", "Enterprise switch", "Aggregation", "WiFi 7", "WiFi 6", "WiFi 5 (legacy)", "G5 camera", "G4 camera (legacy)", "AI camera", "Access", "NVR", "UNAS", "Talk", "EV", ...
  "legacy": false,                     // true if superseded/old gen (G3, AC, US-*, etc.) or not sold in store
  "summary": "≤20 words, what it IS and its niche",
  "jobs": [{"job": "wifi_ceiling", "role": "primary"}],
  "f": {
    "form_factor": "ceiling",          // desktop | rack_1u | rack_2u | rack_mountable_desktop | ceiling | wall | in_wall | outdoor | din | pole | mini | camera_* | reader | module | other
    "requires_console": true,          // needs a UniFi OS console / gateway / Cloud Key to adopt & manage
    "hosts_apps": [],                  // UniFi OS console apps it HOSTS: network, protect, access, talk, connect, drive, innerspace
    "managed_by": "network",           // which app manages it: network | protect | access | talk | connect | drive | standalone
    "power_in": ["poe+"],              // poe | poe+ | poe++ | poe_bt | ac | dc | usb_c | battery | redundant_psu
    "power_draw_w": 21,
    "uplink": "2.5GbE",                // fastest uplink port/type
    "ports": {"rj45_1g": 0, "rj45_2_5g": 1, "rj45_10g": 0, "sfp_1g": 0, "sfp_plus_10g": 0, "sfp28_25g": 0, "qsfp28_100g": 0},
    "poe_out_ports": 0,                // ports that SUPPLY PoE
    "poe_out_types": [],               // poe | poe+ | poe++ | poe_bt_60w | poe_bt_90w
    "poe_budget_w": null,
    "layer": null,                     // switches: "L2" | "L3 lite" | "L3"
    "wan_ports_max": null,             // gateways
    "ips_throughput_gbps": null,       // gateways
    "routing_throughput_gbps": null,
    "max_devices": null,               // managed UniFi devices (consoles)
    "max_clients": 300,                // wifi clients or gateway users
    "wifi_std": "WiFi 7",              // WiFi 5 | WiFi 6 | WiFi 6E | WiFi 7 | null
    "bands": ["2.4", "5", "6"],
    "streams": 6,
    "coverage_m2": 140,
    "outdoor_rated": false,            // IP rating present
    "ip_rating": null,
    "storage": null,                   // e.g. "1x 2.5\" HDD bay", "128GB SSD", "4x 3.5\" bays"
    "max_storage_tb": null,
    "camera": null,                    // {"res": "4K", "fps":30, "night": "IR 30m", "ai": "person/vehicle/LPR", "lens": "...", "audio": "two-way"} or null
    "sensors": [],                     // motion, contact, temp, humidity, leak, smoke, glass_break, light ...
    "redundancy": [],                  // redundant_psu, shadow_mode_ha, ...
    "special": [],                     // salient extras: "built-in WiFi", "LTE backup", "NFC reader", "PoE passthrough", "display", "UPS", "stackable", "etherlighting", ...
    "requires": [],                    // hard dependencies, e.g. "UniFi Access Hub", "PoE++ source (60W)", "UniFi Protect NVR/console", "SFP+ module or DAC"
    "extra": {}
  },
  "gotchas": ["2-6 concrete, spec-grounded buyer traps (needs PoE+ not PoE, no console included, 1G uplink bottleneck, fan noise, no SFP+, PoE budget < sum of ports, requires Access Hub, legacy/EOL, no 6GHz, US-only power...) — name the sibling that fixes it"],
  "best_for": ["..."],
  "not_for": ["..."],
  "confidence": "high"
}
```

## Jobs taxonomy (use these ids; new ones prefixed `new:`)

| job | meaning |
|---|---|
| gateway_router | internet gateway / firewall / router |
| gateway_allinone | gateway + built-in WiFi / switch for small sites |
| console_host | runs UniFi OS apps (Network/Protect/Access controller) |
| switch_poe_edge | access switch powering APs/cameras/phones |
| switch_edge | non-PoE access switch |
| switch_compact | desktop/mini/flex switch for a room or desk |
| switch_core_agg | 10/25/100G aggregation / core |
| switch_industrial | DIN / hardened / outdoor switching |
| wifi_ceiling | ceiling AP |
| wifi_wall | in-wall / wall-plate AP (hospitality, dorms, rooms) |
| wifi_outdoor | outdoor AP / mesh |
| wifi_mesh_extend | plug-in / wireless extender, meshing |
| wifi_highdensity | stadium / mega-capacity |
| wireless_bridge | point-to-point / building-to-building link |
| nvr_recording | video recording / storage for cameras |
| camera_indoor | |
| camera_outdoor | |
| camera_doorbell | |
| camera_ptz_wide | PTZ / 360 / panoramic / long-range |
| alarm_sensor | motion/contact/env sensors, sirens, alarm hubs |
| access_reader | door reader / keypad |
| access_hub_lock | door controller, lock power/relay, hub |
| intercom | intercom / visitor entry |
| storage_nas | network storage / backup |
| internet_backup | LTE/5G/failover/ISP |
| power_backup | UPS / power distribution / PoE power tech |
| voip_phone | phones / Talk |
| iot_premium | EV charging, displays, signage, other premium IoT |
| accessory | modules, cables, mounts, injectors |
