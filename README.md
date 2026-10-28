# catalog-graph

Turns a vendor's product catalog (Shelly, Ubiquiti/UniFi, ham radio gear) into a
typed "upgrade / downgrade / sidegrade" graph and a single-file browser SPA: for
each product and each capability delta (+metering, +PoE budget, legacy->current,
another band...), find the nearest product that realizes that delta while changing
the least else, and say why you'd want it. The ham domain also carries an
inventory/band-ledger planner and a hedonic price model.

Pipeline (per domain, `data/<domain>/`):

1. **fetch** - `scripts/shelly_fetch.py`, `scripts/ubiquiti_fetch.py`, DXE/Shopify
   scrapes for ham -> `data/<domain>/raw/` (not committed; re-fetchable) -> `catalog.json`
2. **normalize** - `scripts/shard.py` splits the catalog; an LLM fills each record
   per `schema/features*.md` -> `data/<domain>/features/<slug>.json`
   (`ant_prep.py` / `shopify_ant.py` / `ant_post.py` for ham antennas, `eham_join.py` adds review ratings)
3. **graph** - `scripts/build_graph.py data/<domain>` with domain rules in
   `scripts/rules/<domain>.py` -> `graph.json`; `pairs_from_features.py` -> `pairs.json`
4. **site** - `scripts/build_site.py data/<domain> site/<domain>.html`
   (inlines `site/template.html` + `inventory.js`/`inv_<domain>.js`/`pricing.js`)

```sh
python3 scripts/build_graph.py data/ubiquiti
python3 scripts/build_site.py data/ubiquiti site/ubiquiti.html && open site/ubiquiti.html
```

The built `graph.json` / `features/` for each domain are committed; raw scrape
caches and built HTML are not. Personal inventory is stored outside the repo.

License: MIT (code). Product data belongs to the respective manufacturers.
