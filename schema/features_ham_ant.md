# Normalized product record — amateur antennas (DX Engineering), one JSON object per antenna

Ground every field in the given name / desc / specs. Unknown → null (not false). Keep it compact: no prose beyond `summary` and `gotchas`.

```jsonc
{
  "id": "pez-ef-allbandkw",            // = slug, verbatim
  "kind": "antenna",                   // always
  "name": "EF-ALLBAND-KW",             // model as the maker writes it (short)
  "title": "Par EndFedz EF-ALLBAND-KW",
  "brand": "Par EndFedz",
  "price": 189.95,                     // numeric from `price`
  "line": "HF end-fed wire",           // short family label: "HF end-fed wire", "HF dipole", "HF OCF dipole", "HF multiband vertical", "HF monoband yagi",
                                       //  "HF tribander yagi", "HF hex beam", "HF log-periodic", "HF mag loop", "HF portable vertical", "HF mobile whip",
                                       //  "V/U base vertical", "V/U yagi", "V/U sat (crossed yagi)", "V/U mobile whip", "HT antenna", "discone (RX)", ...
  "legacy": false,
  "summary": "≤14 words: what it is and its niche",
  "jobs": [{"job": "ant_hf_wire", "role": "primary"}],
  "f": {
    "ant_type": "end-fed",             // dipole | ocf-dipole | end-fed | random-wire | loop-wire | vertical | ground-plane | j-pole | collinear | yagi | quad | hex-beam | moxon | log-periodic | mag-loop | whip | rubber-duck | discone | nvis | other
    "mount": "base",                   // base (fixed home install) | portable (field/POTA, tripod, quick deploy) | mobile (vehicle) | handheld (HT)
    "ant_bands": ["80m","40m","20m","15m","10m"],  // ham TX bands covered AS SOLD (with tuner if the maker says tuner use is intended), from:
                                       //   160m 80m 60m 40m 30m 20m 17m 15m 12m 10m 6m 2m 1.25m 70cm 23cm
    "resonant": true,                  // true = usable without a tuner on the listed bands; false = needs a tuner (non-resonant / random wire / "wide range tuner")
    "tuner_req": null,                 // DXE "Antenna Tuner Requirement" text if given
    "max_w": 1000,                     // SSB/CW PEP rating in W (first number)
    "max_w_digital": 250,              // digital/continuous rating if given
    "gain_dbi": null,                  // dBi; convert dBd → dBi (+2.15); null if not stated
    "elements": null,                  // beams: element count (total)
    "boom_ft": null, "turn_radius_ft": null, "wind_sqft": null,
    "length_ft": 65.6,                 // wire / overall length
    "height_ft": null,                 // verticals / whips: overall height
    "weight_lb": 2.5,
    "radials": null,                   // true = needs radials / counterpoise for proper operation
    "directional": false,              // true for beams (yagi, quad, hex, moxon, LPDA) — needs a rotator
    "polarization": "horizontal",      // horizontal | vertical | circular | null
    "connector": "SO-239",
    "rx_only": false,                  // receive-only (discone, scanner antennas, RX loops)
    "assembled": true,                 // DXE "Assembled" when given
    "extra": {}
  },
  "gotchas": ["0-2 short, concrete traps: 'needs a wide-range tuner', 'needs 30 ft feedpoint height', 'radials required', 'rotator not included', '100 W max — not for amps'"],
  "confidence": "high"                 // medium when bands/type had to be inferred from the name
}
```

## Jobs taxonomy (antennas)

| job | meaning |
|---|---|
| ant_hf_wire | HF wire antennas for a fixed station (dipole, end-fed, OCF, loop) |
| ant_hf_vertical | HF ground-mounted / roof verticals for a fixed station |
| ant_hf_beam | rotatable HF directional antennas (yagi, hex, quad, LPDA, moxon) |
| ant_hf_portable | field / POTA / SOTA HF antennas (tripod verticals, packable wires, buddipole-style) |
| ant_hf_mobile | HF antennas for a vehicle (screwdriver, hamstick, whips) |
| ant_small_space | stealth / limited-space HF (mag loops, attic, flagpole, short loaded) |
| ant_vu_base | VHF/UHF omni base antennas (verticals, collinears, J-poles) |
| ant_vu_beam | VHF/UHF yagis / directional, incl. satellite and weak-signal |
| ant_vu_mobile | VHF/UHF (and HF/VHF/UHF) vehicle antennas |
| ant_ht | handheld (HT) antennas: rubber ducks, whips, roll-up J-poles |
| ant_rx | receive-only / scanner antennas (discone, wideband) |
