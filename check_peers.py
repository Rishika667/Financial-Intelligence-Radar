import json
data = json.load(open("config/sp500_representative_51_2026.json", "r"))
comps = [c["ticker"] for c in data["companies"]]
missing = []
for p in data["peer_groups"]:
    for m in p["members"]:
        if m not in comps:
            missing.append(m)
print("MISSING PEERS:", set(missing))
