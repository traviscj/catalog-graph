# Normalized product record — amateur radio transceivers (Yaesu, Icom, Kenwood, FlexRadio via DX Engineering), one JSON per radio

Unknown → null (not false). Ground everything in the DXE specs/overview text you were given; you may use well-established
public knowledge of the model to fill obvious gaps (e.g. FT-991A has D-STAR? no — C4FM), but set confidence "medium" when you do.
Variants that are the same radio (e.g. "-ASP" bundles with a programming cable, open-box, "Field" vs "Optima" battery packs)
stay separate records but say what the variant is in `summary` and `gotchas`.

```jsonc
{
  "id": "ysu-ftdx-10",                  // = DXE slug, verbatim
  "name": "FTDX10",                     // model as the maker writes it
  "title": "Yaesu FTDX10",
  "brand": "Yaesu",
  "price": 1499.95,                     // DXE current price (numeric, from `price`), list price goes in extra.list_price
  "line": "HF base (hybrid SDR)",       // short family label: "HF flagship", "HF base", "HF/VHF/UHF all-mode", "HF portable/QRP", "HF mobile",
                                        //  "VHF/UHF all-mode (sat)", "VHF/UHF mobile", "VHF/UHF D-STAR mobile", "C4FM mobile", "HT", "D-STAR HT", "C4FM HT", ...
  "legacy": false,                      // true if discontinued / superseded by a current sibling (e.g. IC-7300 vs IC-7300MK2)
  "summary": "≤20 words, what it IS and its niche",
  "jobs": [{"job": "hf_base", "role": "primary"}, {"job": "ft8_digital", "role": "secondary"}],
  "f": {
    "form_factor": "base",              // base | mobile | portable | handheld
    "bands_tx": ["160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m"],   // ham TX bands, from: 160m 80m 60m 40m 30m 20m 17m 15m 12m 10m 6m 4m 2m 1.25m 70cm 23cm
    "hf": true,                         // transmits on HF (160–10m)
    "vhf_uhf": false,                   // transmits on 2m and/or 70cm
    "rx_range": "0.030–75 MHz",         // general-coverage receive, text
    "power_w": {"hf": 100, "6m": 100, "2m": null, "70cm": null, "23cm": null},   // max RF out per band group
    "modes": ["SSB","CW","AM","FM","RTTY","PSK","DATA"],                         // add "D-STAR","C4FM","DMR" for digital voice
    "digital_voice": [],                // [] | ["D-STAR"] | ["C4FM"] | ["DMR"] ...
    "receiver_arch": "hybrid SDR",      // superhet | direct-sampling SDR | hybrid SDR | narrowband SDR | FM (HT/mobile) | null
    "band_scope": "real-time scope + waterfall", // null if none
    "display": "5in color touch",       // short
    "dual_receive": false,              // truly independent second receiver (two signals at once, separate audio paths)
    "dual_watch": false,                // V/V, U/U or V/U dual watch / dual band display (mobiles/HTs) — say which in extra if notable
    "atu": true,                        // internal antenna tuner (HF)
    "usb_single_cable": true,           // one USB cable gives CAT + audio codec (easy FT8/WSJT-X)
    "lan_remote": false,                // built-in LAN/WLAN remote operation (no extra PC box)
    "wifi_bt": [],                      // "Bluetooth", "WLAN"
    "gps": false,
    "aprs": false,                      // built-in APRS (or D-PRS for D-STAR — note in extra)
    "full_duplex_sat": false,           // full-duplex cross-band for satellites
    "crossband_repeat": false,
    "detachable_head": false,           // separable control head (mobile install)
    "headless": false,                  // true = no front panel: needs a PC/tablet (SmartSDR) or separate controller (Maestro) to operate (FlexRadio non-M models)
    "power_source": "13.8 VDC external", // "13.8 VDC external" | "internal AC PSU" | "internal battery + 13.8 VDC" | "Li-ion pack"
    "tx_current_a": 23,
    "battery": null,                    // internal/included battery text, e.g. "BP-272 Li-ion 1880 mAh", "FBA-? 13.8V pack (Field model)"
    "ip_rating": null,                  // "IPX7", "IP54", ...
    "antenna_ports": 1,
    "rx_antenna_in": false,             // dedicated receive-antenna input
    "roofing_filters": "12k/3k/500/300(opt)",
    "memories": 99,
    "weight_kg": 5.9,
    "size_mm": "266×91×263",
    "special": [],                      // salient extras: "external monitor out", "SD recording", "voice keyer", "IF out", "2 receivers", "touch screen", "QRP 6W internal battery", "SPA-1 amp option", ...
    "requires": [],                     // hard needs to be useful: "13.8V 25A power supply", "external ATU for HF", "programming cable", "separately sold battery", ...
    "extra": {}
  },
  "gotchas": ["2-6 concrete, spec-grounded buyer traps — name the sibling that fixes it (e.g. 'no internal ATU — FT-710 AESS has one', '10W on HF — IC-705 is QRP; IC-7300MK2 for 100W', 'no 2m/70cm — FT-991A covers HF-70cm', 'needs a 23A 13.8V supply (not included)', 'single receiver: no dual watch for split DX', 'analog FM only — no digital voice')"],
  "best_for": ["..."],
  "not_for": ["..."],
  "confidence": "high"
}
```

## Jobs taxonomy (use these ids; new ones prefixed `new:`)

| job | meaning |
|---|---|
| hf_base | home HF station: 160–6m from the shack |
| hf_contest_dx | top-end receiver for pileups, contests, weak DX (roofing filters, dual RX, phase noise) |
| hf_portable | field/POTA/SOTA HF: battery, light, low power |
| hf_mobile | HF from a vehicle (compact, separable head) |
| allband_allmode | one box for HF + 6m + 2m/70cm, all modes |
| vhf_uhf_allmode | 2m/70cm SSB/CW/FM: weak-signal, satellites, EME |
| satellite | full-duplex V/U for FM/linear satellites |
| vhf_uhf_mobile | 2m/70cm FM rig for the car or a base FM station |
| vhf_uhf_handheld | handheld (HT) for repeaters, events, emcomm |
| digital_voice | D-STAR / C4FM / DMR voice and data |
| aprs | position reporting / messaging (APRS or D-PRS) |
| ft8_digital | weak-signal data modes (FT8/FT4/RTTY) via single-cable USB |
| remote_operation | run the station over LAN/internet |
| first_radio | cheap, simple entry radio for a new Technician licensee |
| emcomm | rugged, waterproof, long battery, crossband repeat for public service |
| accessory | not a radio |
