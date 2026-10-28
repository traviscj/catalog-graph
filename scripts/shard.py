import json, sys, re
r = [x for x in json.load(open(sys.argv[1])) if x["specs"] or x["kb_sections"]]
n = int(sys.argv[3])
for i in range(n):
    part = r[i::n]
    json.dump(part, open(f"{sys.argv[2]}/shard{i}.json", "w"), indent=1, ensure_ascii=False)
    print(i, len(part), sum(len(json.dumps(x)) for x in part))
