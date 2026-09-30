import json
import logging
import time
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
    operating_margin_deterioration,
    cash_conversion,
    fcf_deterioration,
    leverage,
    liquidity,
    dilution,
)
from .events import extract_events
from .peers import load_peer_groups, peer_context_for_company

logger = logging.getLogger(__name__)

FORMS = {"10-K", "10-Q", "8-K", "20-F", "6-K", "10-K/A", "10-Q/A", "8-K/A"}


def load_universe(path="config/sp500_representative_51_2026.json"):
    return json.loads(Path(path).read_text())["companies"]


def filing_index(submissions, cik):
    """Build accession -> filing metadata index from SEC submissions."""
    r = submissions.get("filings", {}).get("recent", {})
    if not r:
        return {}
    out = {}
    for i, acc in enumerate(r.get("accessionNumber", [])):
        if r.get("form", [""])[i] not in FORMS:
            continue
        out[acc.replace("-", "")] = {
            "accessionNumber": acc,
            "form": r.get("form", [""])[i],
            "filingDate": r.get("filingDate", [""])[i],
            "source_url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{r.get('primaryDocument', [''])[i]}",
        }
    return out


def _latest(items, metric, pt):
    """Sort relevant observations descending by period_end."""
    x = [
        o
        for o in items
        if o.metric == metric
        and o.period_type == pt
        and o.value is not None
    ]
    return sorted(x, key=lambda o: o.period_end, reverse=True)


def _comparable_pair(items, metric, pt):
    """Select the latest observation and its prior-year counterpart.

    The signal gate, rather than selection, owns comparability decisions so an
    invalid prior can produce an explicit suppressed signal instead of being
    silently replaced by an older period.
    """
    observations = _latest(items, metric, pt)
    if not observations:
        return None, None
    current = observations[0]
    prior = next(
        (
            candidate
            for candidate in observations[1:]
            if 350 <= (current.period_end - candidate.period_end).days <= 380
        ),
        None,
    )
    return current, prior


def _ratio(a, b, name):
    """Compute a derived ratio observation.

    Uses unit="pure" for dimensionless ratios so the _ok() currency
    compatibility gate correctly excludes them from monetary unit checks.
    """
    from .models import Observation, DataQuality

    valid = (
        a.company == b.company
        and a.unit == b.unit
        and a.period_end == b.period_end
        and a.period_type == b.period_type
        and a.comparable
        and b.comparable
        and a.value is not None
    )

    if not valid or b.value in (None, 0):
        return Observation(
            a.company, name, None, "pure", a.period_end, a.period_type,
            DataQuality.CALCULATION_INVALID, comparable=False,
        )
    return Observation(
        a.company, name, a.value / b.value, "pure", a.period_end,
        a.period_type, DataQuality.DERIVED, a.provenance + b.provenance,
        derived_from=(f"{a.metric} {a.period_end.isoformat()} {a.period_type}", f"{b.metric} {b.period_end.isoformat()} {b.period_type}"),
        period_start=a.period_start
    )


def evaluate(company, items, sector="Unknown"):
    """Evaluate all 10 deterministic signals for a company's observations using canonical metrics."""
    from .metrics import derive_analytical_metrics, get_comparison_pair
    derived = derive_analytical_metrics(items)
    # Don't mutate the original items array permanently outside, but we can combine them here
    all_obs = items + derived
    
    out = []

    def pair(m, pt="QUARTER"):
        return get_comparison_pair(all_obs, m, pt, "yoy")
        
    def pair_instant(m):
        return get_comparison_pair(all_obs, m, "INSTANT", "yoy")

    def _suppress(id):
        from .models import Signal
        if "DEBT" in id:
            exp = "Debt/Operating Income is suppressed for financial institutions because the metric is not directly comparable with non-financial corporate capital structures."
        elif "INVENTORY" in id:
            exp = "Inventory Divergence is suppressed for financial institutions because inventory dynamics are generally not applicable."
        elif "RECEIVABLES" in id:
            exp = "Receivables/Revenue Divergence is suppressed for financial institutions."
        elif "GROSS" in id:
            exp = "Gross Margin is suppressed for financial institutions."
        else:
            exp = "Not applicable to Financials sector."
        return Signal(id, company, "UNKNOWN", "LOW", exp, (), suppressed_reason="Sector Context (Financials)")

    rev, prevrev = pair("revenue")
    ar, prevar = pair_instant("accounts_receivable")
    inv, previnv = pair_instant("inventory")

    if sector == "Financials":
        out.append(_suppress("RECEIVABLES_REVENUE_DIVERGENCE"))
        out.append(_suppress("INVENTORY_SALES_DIVERGENCE"))
        out.append(_suppress("FREE_CASH_FLOW_DETERIORATION"))
        out.append(_suppress("DEBT_OPERATING_INCOME_DETERIORATION"))
        out.append(_suppress("LIQUIDITY_COMPRESSION"))

    if rev and prevrev and ar and prevar:
        if sector != "Financials":
            out.append(divergence("RECEIVABLES_REVENUE_DIVERGENCE", ar, rev, prevar, prevrev))
            
    if rev and prevrev and inv and previnv:
        if sector != "Financials":
            out.append(divergence("INVENTORY_SALES_DIVERGENCE", inv, rev, previnv, prevrev))

    # Margin compressions now use the CANONICAL metric
    gm, pgm = pair("gross_margin")
    if gm and pgm:
        if sector != "Financials":
            out.append(margin_compression(gm, pgm))

    om, pom = pair("operating_margin")
    if om and pom:
        out.append(operating_margin_deterioration(om, pom))

    ocf, pocf = pair("operating_cash_flow")
    ni, pni = pair("net_income")
    if ocf and ni and pocf and pni:
        out.append(cash_conversion(ocf, ni, pocf, pni))

    fcf, pfcf = pair("free_cash_flow")
    if fcf and pfcf:
        if sector != "Financials":
            out.append(fcf_deterioration(fcf, pfcf))

    # For leverage, we compare Debt directly with Op Income as before, since it requires INSTANT vs QUARTER logic.
    debt_cur, pdebt = pair_instant("debt")
    op, pop = pair("operating_income")
    if debt_cur and op and pdebt and pop:
        if sector != "Financials":
            out.append(leverage(debt_cur, op, pdebt, pop))

    cash, pcash = pair_instant("cash_and_equivalents")
    cl, pcl = pair_instant("current_liabilities")
    if cash and cl and pcash and pcl:
        if sector != "Financials":
            out.append(liquidity(cash, cl, pcash, pcl))

    shares, pshares = pair("share_count")
    if shares and pshares:
        out.append(dilution(shares, pshares))

    out = [x for x in out if x]
    return out + cluster(out)


def compute_peer_context(company, observations, peer_groups_path="config/sp500_representative_51_2026.json"):
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
    
    # Derive Analytical Spine
    from .metrics import derive_analytical_metrics
    derived = derive_analytical_metrics(obs)
    obs.extend(derived)
    
    save_observations(c, obs)
    from .store import save_filings
    save_filings(c, cik, filings)

    # Clear old signals before re-evaluation
    clear_signals(c, ticker)

    # Evaluate signals
    sig = evaluate(ticker, obs, company.get("sector", "Unknown"))
    save_signals(c, sig)

    events_found = _extract_events_from_submissions(ticker, filings, c, client)

    return {
        "observations": len(obs),
        "signals": len(sig),
        "peer_group": None,
        "events": events_found,
    }


def _extract_events_from_submissions(ticker, filings, c, client):
    """Extract events from actual 8-K filing texts by retrieving from SEC EDGAR.

    Retrieval failures are logged (observable) but do not break the pipeline.
    """
    count = 0
    # Process only the 5 most recent 8-Ks to respect SEC pacing/volume
    recent_8ks = sorted(
        [f for f in filings.values() if f.get("form") in ("8-K", "8-K/A")],
        key=lambda x: x.get("filingDate", ""),
        reverse=True,
    )[:5]

    for filing in recent_8ks:
        url = filing.get("source_url")
        if url:
            try:
                pause = client.delay - (time.monotonic() - client.last)
                if pause > 0:
                    time.sleep(pause)
                r = client.s.get(url, timeout=30)
                client.last = time.monotonic()
                r.raise_for_status()

                text = r.text
                events = extract_events(ticker, filing, text)
                if events:
                    save_events(c, events)
                    count += len(events)
            except Exception as exc:
                logger.warning(
                    "Event extraction failed for %s filing %s: %s",
                    ticker, filing.get("accessionNumber", "?"), exc,
                )
    return count


def ingest_events(company, filing, text, c):
    """Ingest events from filing document text."""
    save_events(c, extract_events(company["ticker"], filing, text))


def refresh_peer_contexts(c, active_tickers):
    import logging
    logger = logging.getLogger(__name__)
    
    from .store import load_observations_for_companies, clear_peer_context, save_peer_context
    from .peers import load_peer_groups, peer_context_for_company
    pg = load_peer_groups("config/sp500_representative_51_2026.json")
    
    # Need to load observations for all peers of active tickers, not just active tickers
    tickers_to_load = set(active_tickers)
    from .peers import find_peer_group
    for t in active_tickers:
        group_id, peers = find_peer_group(t, pg)
        if peers:
            tickers_to_load.update(peers)
            
    all_obs = load_observations_for_companies(c, list(tickers_to_load))
    
    for t in active_tickers:
        clear_peer_context(c, t)
        peer_ctx = peer_context_for_company(t, all_obs, pg)
        save_peer_context(c, t, peer_ctx)

def validate_portfolio_csv(df, universe_tickers):
    if df.empty:
        return False, "CSV is empty."
        
    df.columns = [str(c).strip().lower() for c in df.columns]
    required = ["ticker", "shares", "weight", "cost_basis"]
    
    for req in required:
        if req not in df.columns:
            return False, f"CSV must contain '{req}' column."
            
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    
    if df["ticker"].duplicated().any():
        return False, "CSV contains duplicate tickers."
        
    for t in df["ticker"]:
        if t not in universe_tickers:
            return False, f"Ticker {t} is not in the 50-company universe."
            
    try:
        df["shares"] = df["shares"].astype(float)
        df["weight"] = df["weight"].astype(float)
        df["cost_basis"] = df["cost_basis"].astype(float)
    except ValueError:
        return False, "Numeric columns contain invalid non-numeric data."
        
    if df.isna().any().any():
        return False, "CSV contains NaN or blank values."
        
    if (df["shares"] <= 0).any():
        return False, "Column 'shares' cannot be zero or negative."
        
    if (df["cost_basis"] <= 0).any():
        return False, "Column 'cost_basis' cannot be zero or negative."
        
    if (df["weight"] <= 0).any() or (df["weight"] > 1).any():
        return False, "Column 'weight' must be between 0 and 1."
        
    total_weight = df["weight"].sum()
    if abs(total_weight - 1.0) > 0.01:
        return False, f"Total weight must sum to 1.0. Current sum is {total_weight:.4f}."
        
    return True, ""

def calculate_data_readiness(ticker, c):
    from .store import rows
    from .models import ReadinessState
    
    errs = rows(c, "SELECT count(*) as c FROM signals WHERE company=? AND signal_id='INGESTION_FAILED'", (ticker,))
    if errs and errs[0]['c'] > 0:
        return ReadinessState.FAILED, "Ingestion failed"
        
    obs = rows(c, "SELECT * FROM observations WHERE company=?", (ticker,))
    if not obs:
        return ReadinessState.NOT_READY, "No observations found"
        
    core = {'revenue', 'net_income', 'operating_income', 'operating_cash_flow', 'cash_and_equivalents'}
    
    valid_metrics = set()
    for o in obs:
        if o['value'] is not None and o['quality'] in ('REPORTED', 'DERIVED') and o['comparable'] == 1 and o['provenance'] and o['provenance'] != "[]":
            valid_metrics.add(o['metric'])
            
    missing = core - valid_metrics
    if not missing:
        return ReadinessState.READY, "All core metrics successfully validated and comparable."
    elif len(valid_metrics) > 0:
        return ReadinessState.PARTIAL, f"Missing or invalid evidence for: {', '.join(missing)}"
    else:
        return ReadinessState.NOT_READY, "No valid comparable evidence found."
