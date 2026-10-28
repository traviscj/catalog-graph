import json, collections, sys
r = json.load(open(sys.argv[1]))
for x in r:
    if x["specs"]:
        print(f'{x["price"] or 0:7.2f} {x["product_type"][:22]:22s} {x["family"]}')
keys = collections.Counter(f"{s}::{k}" for x in r for s, d in x["specs"].items() for k in d)
print(len(keys)); print([k for k, _ in keys.most_common(100)])
