import json
data = json.load(open("config/sp500_representative_51_2026.json", "r"))

data["companies"].append({
    "ticker": "AMD",
    "cik": "0000002488",
    "name": "Advanced Micro Devices, Inc.",
    "gics_sector": "Information Technology",
    "gics_industry": "Semiconductors",
    "universe_type": "PEER_REFERENCE_UNIVERSE"
})
data["companies"].append({
    "ticker": "PFE",
    "cik": "0000078003",
    "name": "Pfizer Inc.",
    "gics_sector": "Health Care",
    "gics_industry": "Pharmaceuticals",
    "universe_type": "PEER_REFERENCE_UNIVERSE"
})

with open("config/sp500_representative_51_2026.json", "w") as f:
    json.dump(data, f, indent=4)
