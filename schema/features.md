# Normalized product record (stage 2 output) — one JSON file per product

Domain-agnostic envelope + domain-specific `f` (features). Shelly `f` keys below.
Unknown → `null` (NOT false). Only assert what specs/kb_sections/blurb support.

```jsonc
{
  "id": "shelly-1-mini-gen4",          // kebab slug of family
  "name": "Shelly 1 Mini Gen4",
  "price": 24.99,
  "line": "Gen4",                      // Gen1 | Plus(Gen2) | Gen3 | Gen4 | Pro | Wave | Wave Pro | BLU | Pill | 3rd-party | Accessory
  "summary": "≤20 words, what it IS",
  "jobs": [ {"job": "switch_load", "role": "primary"}, {"job": "retrofit_wall_switch", "role": "secondary"} ],
  "f": {
    "form_factor": "in_wall_mini",     // in_wall | in_wall_mini | din_rail | plug | battery_sensor | wired_sensor | wall_device | bulb | addon | accessory | hub_display | camera | clamp_ct
    "mains_powered": true,
    "supply": "110-240VAC",            // free text, normalized
    "dc_supply": false,                // can run from 12/24V DC
    "battery": null,                   // e.g. "CR2032", "2xAA", "rechargeable"
    "neutral_required": true,
    "channels": 1,                     // switched/dimmed/metered channels
    "output_type": "dry_relay",        // dry_relay | wet_relay | triac_dimmer | mosfet_dimmer | 0-10v | dali | pwm_rgbw | ssr | none
    "max_current_a": 8,                // per channel, AC resistive
    "max_power_w": 2000,
    "dc_switching": "5A/30V",          // or null
    "power_metering": "none",          // none | per_channel | whole_circuit | 1ph_clamp | 3ph_clamp | 2ch_clamp
    "metering_max_a": null,            // CT/clamp range
    "dimming": null,                   // trailing | leading | both | 0-10v | 1-10v | dali | pwm | null
    "cover_control": false,
    "color_light": null,               // rgb | rgbw | rgbww | cct | null
    "inputs": "1 switch input (SW)",   // free text
    "input_count": 1,
    "sensors": ["internal_temp"],      // temp, humidity, lux, motion, presence_mmwave, contact, flood, gas, vibration, tilt, distance, button, voltage, ...
    "radios": ["wifi", "bluetooth", "zigbee"],  // wifi | ethernet | bluetooth | zigbee | zwave | zwave_lr | lora | matter_over_wifi | thread
    "matter": null,
    "ble_gateway": true,               // can relay BLU devices
    "zwave_repeater": null,
    "local_api": true,                 // HTTP/RPC local control
    "mqtt": true,
    "scripting": true,
    "ul_listed": false,
    "protections": ["overtemp"],       // overtemp, overcurrent, overvoltage, overpower, undervoltage
    "temp_range_c": "-20..40",
    "size_mm": "29x34x16",
    "addon_port": false,               // supports Shelly add-on / sensor add-on
    "requires": [],                    // ids/descriptions of things it CAN'T work without (e.g. "Shelly gateway / BLE gateway", "Z-Wave controller", "Shelly Plus/Pro host")
    "extra": {}                        // anything else salient (e.g. {"display": "10in"})
  },
  "gotchas": [                         // spec-grounded, specific, short; what bites a buyer
    "No power metering — use 1PM Mini Gen4 if you need it",
    "8A max: not for >1900W loads (space heaters, water heaters)"
  ],
  "best_for": ["≤8A lighting circuit behind a wall switch where box space is tight"],
  "not_for": ["metering", "high-current resistive loads"],
  "confidence": "high"                 // high | medium | low (how well specs covered it)
}
```

## Jobs taxonomy (use these ids; add new only if truly needed, prefix `new:`)

| job | meaning |
|---|---|
| switch_load | on/off a mains load (light, fan, pump) |
| switch_high_current | ≥16A loads: water heater, EV, heater, contactor coil |
| switch_low_voltage | switch DC / dry contact (garage door, gate, doorbell, HVAC call, boiler) |
| retrofit_wall_switch | make an existing dumb wall switch/circuit smart behind the switch |
| meter_circuit | measure power/energy of a load it also switches |
| meter_panel | whole-home / sub-panel / solar / 3-phase energy monitoring via clamps |
| dim_light | dim incandescent/LED mains lighting |
| dim_lowvolt_driver | drive 0-10V / 1-10V / DALI dimmable drivers |
| color_light | RGB/RGBW/CCT strips or bulbs |
| control_cover | roller shutters, blinds, curtains, garage doors (motor up/down) |
| input_trigger | turn buttons/switches/contacts into scene triggers (no load) |
| remote_button | wireless/battery button or remote |
| sense_temp_humidity | |
| sense_motion_presence | PIR motion or mmWave presence |
| sense_contact | door/window open-close |
| sense_leak | water leak / flood |
| sense_gas | gas leak |
| sense_distance_level | tank level, distance |
| sense_analog | read 0-10V / analog / generic sensors (Uni, Pill) |
| thermostat_hvac | TRV, HVAC, heating control |
| plug_in | no-wiring plug-in control |
| zwave_mesh | user is on a Z-Wave controller ecosystem |
| ble_gateway_range | extend/bridge BLU devices |
| dashboard_hub | wall display / local control panel |
| camera | video |
| irrigation | sprinklers |
| diy_maker | dev boards, modules, add-ons for tinkerers |
| accessory | passive part (cable, bracket, CT, decoupler) |
