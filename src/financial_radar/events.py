import re
import hashlib

# Conservative taxonomy: only extract events matching these patterns.
# Precision over recall — provenance matters more than coverage.
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
    """Extract corporate events from filing text using conservative regex patterns.

    Returns a list of event dicts with id, company, type, filing metadata,
    and a snippet with provenance context.
    """
    if not text or not filing:
        return []
    out = []
    accession = filing.get("accessionNumber", "")
    for typ, pattern in PATTERNS.items():
        m = re.search(pattern, text, re.I)
        if m:
            event_id = hashlib.sha1(
                f"{company}{accession}{typ}".encode()
            ).hexdigest()[:16]
            snippet = text[
                max(0, m.start() - SNIPPET_BEFORE) : m.end() + SNIPPET_AFTER
            ].replace("\n", " ").strip()
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
                    "extraction_version": "v1.0",
                }
            )
    return out
