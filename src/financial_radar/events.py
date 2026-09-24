import re
import hashlib

PATTERNS = {
    "acquisition": r"\b(acquisitions?|mergers?|acquired|business combinations?)\b",
    "divestiture": r"\b(divestitures?|dispose[ds]?|sold .{0,30}business)\b",
    "debt": r"\b(refinanc|credit facility|notes due|debt issuance|term loan)\b",
    "equity": r"\b(equity offering|stock issuance|secondary offering)\b",
    "buyback": r"\b(repurchases?|buybacks?|share repurchases?)\b",
    "restructuring": r"\brestructur",
    "material_agreement": r"material definitive agreement",
    "legal": r"\b(litigation|lawsuits?|legal proceedings?|settlements?)\b",
    "segment": r"\b(segment change|reportable segments?|operating segments?)\b",
}

SNIPPET_BEFORE = 100
SNIPPET_AFTER = 200

def extract_events(company, filing, text):
    if not text or not filing:
        return []
    
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    out = []
    accession = filing.get("accessionNumber", "")
    for typ, pattern in PATTERNS.items():
        m = re.search(pattern, clean_text, re.I)
        if m:
            prefix = clean_text[max(0, m.start() - 40) : m.start()].lower()
            if any(neg in prefix for neg in ["did not", "does not", "no ", "not "]):
                continue
            
            event_id = hashlib.sha1(
                f"{company}{accession}{typ}".encode()
            ).hexdigest()[:16]
            snippet = clean_text[
                max(0, m.start() - SNIPPET_BEFORE) : m.end() + SNIPPET_AFTER
            ].strip()
            out.append(
                {
                    "id": event_id,
                    "company": company,
                    "type": typ,
                    "filing_date": filing.get("filingDate"),
                    "accession": accession,
                    "form": filing.get("form"),
                    "source_url": filing.get("source_url"),
                    "description": snippet,
                    "extraction_version": "v1.1",
                }
            )
    return out
