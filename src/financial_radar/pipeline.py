"""The single local production flow: SEC -> raw -> normalize -> SQLite -> signals/events/peers."""
import json
from pathlib import Path

from .core import SECClient, free_cash_flow
from .normalization import extract_companyfacts
from .store import (
    save_observations,
    save_watchlist,
    save_signals,
    save_events,
    save_peer_context,
    clear_signals,
    clear_peer_context,
)
from .signals import divergence, margin_compression, cluster
from .signals_phase2 import (
    operating_deleverage,
    cash_conversion,
    fcf_deterioration,
    leverage,
    liquidity,
    dilution,
)
from .events import extract_events
from .peers import load_peer_groups, peer_context_for_company

FORMS = {"10-K", "10-Q", "8-K", "20-F", "6-K", "10-K/A", "10-Q/A"}


def load_universe(path="config/universe.json"):
    return json.loads(Path(path).read_text())["companies"]


def filing_index(submissions, cik):
    """Build accession -> filing metadata index from SEC submissions."""
    r = submissions.get("filings", {}).get("recent", {})
    out = {}
    accession_numbers = r.get("accessionNumber", [])
    for i, accession in enumerate(accession_numbers):
        form = r.get("form", [None] * len(accession_numbers))[i]
        if form in FORMS:
            doc = r.get("primaryDocument", [""] * len(accession_numbers))[i]
            out[accession.replace("-", "")] = {
                "accessionNumber": accession,
                "form": form,
                "filingDate": r.get("filingDate", [None] * len(accession_numbers))[i],
                "source_url": (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{int(cik)}/{accession.replace('-', '')}/{doc}"
                ),
            }
    return out


def _latest(items, metric, pt):
    """Return observations for a metric/period_type sorted by period_end descending."""
    x = [
        o
        for o in items
        if o.metric == metric
        and o.period_type == pt
        and o.value is not None
        and o.comparable
    ]
    return sorted(x, key=lambda o: o.period_end, reverse=True)


def _ratio(a, b, name):
    """Compute a derived ratio observation."""
    from .models import Observation, DataQuality

    if b.value in (None, 0):
        return Observation(
            a.company, name, None, "ratio", a.period_end, a.period_type,
            DataQuality.CALCULATION_INVALID, comparable=False,
        )
    return Observation(
        a.company, name, a.value / b.value, "ratio", a.period_end,
        a.period_type, DataQuality.DERIVED, a.provenance + b.provenance,
    )


def evaluate(company, items):
    """Evaluate all 10 deterministic signals for a company's observations."""
    pt = "QUARTER"
    out = []

    def pair(m):
        x = _latest(items, m, pt)
        return (x[0], x[1]) if len(x) > 1 else (None, None)

    rev, prevrev = pair("revenue")
    ar, prevar = pair("accounts_receivable")
    inv, previnv = pair("inventory")

    # Signal 1: Receivables-revenue divergence
    if rev and prevrev and ar and prevar:
        out.append(divergence("RECEIVABLES_REVENUE_DIVERGENCE", ar, rev, prevar, prevrev))
    # Signal 2: Inventory-sales divergence
    if rev and prevrev and inv and previnv:
        out.append(divergence("INVENTORY_SALES_DIVERGENCE", inv, rev, previnv, prevrev))

    gp, pgp = pair("gross_profit")
    op, pop = pair("operating_income")
    ni, pni = pair("net_income")
    ocf, pocf = pair("operating_cash_flow")
    debt_cur, pdebt = pair("debt")
    cash, pcash = pair("cash_and_equivalents")
    cl, pcl = pair("current_liabilities")
    shares, pshares = pair("share_count")
    cap, pcap = pair("capex")

    # Signal 3: Gross-margin compression
    if gp and rev and pgp and prevrev:
        out.append(
            margin_compression(
                _ratio(gp, rev, "gross_margin"),
                _ratio(pgp, prevrev, "gross_margin"),
            )
        )
    # Signal 4: Operating deleverage
    if op and rev and pop and prevrev:
        out.append(
            operating_deleverage(
                _ratio(op, rev, "operating_margin"),
                _ratio(pop, prevrev, "operating_margin"),
            )
        )
    # Signal 5: Earnings-cash conversion deterioration
    if ocf and ni and pocf and pni:
        out.append(cash_conversion(ocf, ni, pocf, pni))
    # Signal 6: FCF deterioration
    if ocf and cap and pocf and pcap:
        out.append(
            fcf_deterioration(
                free_cash_flow(ocf, cap), free_cash_flow(pocf, pcap)
            )
        )
    # Signal 7: Leverage/interest burden
    if debt_cur and op and pdebt and pop:
        out.append(leverage(debt_cur, op, pdebt, pop))
    # Signal 8: Liquidity compression
    if cash and cl and pcash and pcl:
        out.append(liquidity(cash, cl, pcash, pcl))
    # Signal 9: Share-count dilution
    if shares and pshares:
        out.append(dilution(shares, pshares))

    # Signal 10: Multi-factor deterioration cluster
    out = [x for x in out if x]
    return out + cluster(out)


def compute_peer_context(company, observations, peer_groups_path="config/peer_groups.json"):
    """Compute peer context for a company using configured peer groups."""
    try:
        pg = load_peer_groups(peer_groups_path)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"group_id": None, "contexts": [], "version": None}
    return peer_context_for_company(company, observations, pg)


def ingest_company(client, c, company):
    """Full ingestion: SEC fetch -> normalize -> signals -> peers -> persist."""
    ticker = company["ticker"]
    cik = company["cik"]

    # Fetch from SEC
    sub = client.submissions(cik)
    facts = client.company_facts(cik)
    filings = filing_index(sub, cik)

    # Normalize observations
    obs = extract_companyfacts(ticker, cik, facts, filings)
    save_observations(c, obs)

    # Clear old signals before re-evaluation
    clear_signals(c, ticker)

    # Evaluate signals
    sig = evaluate(ticker, obs)
    save_signals(c, sig)

    # Peer context
    clear_peer_context(c, ticker)
    peer_ctx = compute_peer_context(ticker, obs)
    save_peer_context(c, ticker, peer_ctx)

    # Extract events from 8-K filing descriptions (from submissions metadata)
    events_found = _extract_events_from_submissions(ticker, filings, c)

    return {
        "observations": len(obs),
        "signals": len(sig),
        "peer_group": peer_ctx.get("group_id"),
        "events": events_found,
    }


def _extract_events_from_submissions(ticker, filings, c):
    """Extract events from filing metadata descriptions.

    Note: Full 8-K text extraction requires downloading filing documents.
    For the MVP, we extract events from available filing metadata.
    The extract_events function can be called separately with full text
    for deeper extraction.
    """
    count = 0
    for acc, filing in filings.items():
        if filing.get("form") in ("8-K",):
            # Use form type and accession as minimal event signal
            description = f"{filing.get('form', '')} filing"
            events = extract_events(ticker, filing, description)
            if events:
                save_events(c, events)
                count += len(events)
    return count


def ingest_events(company, filing, text, c):
    """Ingest events from filing document text."""
    save_events(c, extract_events(company["ticker"], filing, text))
