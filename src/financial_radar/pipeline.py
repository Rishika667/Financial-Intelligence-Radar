import json
import logging
import time
from .models import Signal
from pathlib import Path

from .core import SECClient
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
from .signals import (
    divergence, gross_margin_compression, operating_margin_deterioration,
    cash_conversion, fcf_deterioration, leverage, liquidity, dilution, cluster
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
            if not acc:
                continue
            forms = r.get("form", [])
            form = forms[i] if i < len(forms) else ""
            if form not in FORMS:
                continue
            
            pdocs = r.get("primaryDocument", [])
            pdoc = pdocs[i] if i < len(pdocs) else ""
            
            fdates = r.get("filingDate", [])
            fdate = fdates[i] if i < len(fdates) else ""
            
            source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{pdoc}" if pdoc else None
            out[acc.replace("-", "")] = {
                "accessionNumber": acc,
                "form": form,
                "filingDate": fdate,
                "source_url": source_url,
            }
    return out


def evaluate(company, items, sector="Unknown"):
    out = []
    
    # Sector Policy Definition
    SECTOR_POLICY = {
        "RECEIVABLES_REVENUE_DIVERGENCE": {"Financials": "Receivables/Revenue Divergence is suppressed for financial institutions."},
        "INVENTORY_SALES_DIVERGENCE": {"Financials": "Inventory Divergence is suppressed for financial institutions because inventory dynamics are generally not applicable."},
        "FREE_CASH_FLOW_DETERIORATION": {"Financials": "Free Cash Flow is suppressed for financial institutions because operating cash flow represents changes in operating assets (loans/deposits)."},
        "DEBT_OPERATING_INCOME_DETERIORATION": {"Financials": "Debt/Operating Income is suppressed for financial institutions because debt is raw material, not just capital structure."},
        "LIQUIDITY_COMPRESSION": {"Financials": "Corporate liquidity ratios (Current/Quick) are suppressed for financial institutions."},
        "GROSS_MARGIN_COMPRESSION": {"Financials": "Gross Margin is suppressed for financial institutions."}
    }
    
    def pair(m):
        from .metrics import get_comparison_pair
        return get_comparison_pair(items, m, "QUARTER", "yoy")

    def _execute_signal(signal_id, func, curr, prior):
        if not curr or not prior: return None
        if signal_id in SECTOR_POLICY and sector in SECTOR_POLICY[signal_id]:
            from .models import Signal
            exp = SECTOR_POLICY[signal_id][sector]
            return Signal(signal_id, company, "UNKNOWN", "LOW", exp, (), suppressed_reason=f"Sector Context ({sector})")
        return func(curr, prior)

    from .signals import divergence, gross_margin_compression, operating_margin_deterioration, cash_conversion, fcf_deterioration, leverage, liquidity, dilution, cluster

    ar_rev, par_rev = pair("receivables_revenue_ratio")
    out.append(_execute_signal("RECEIVABLES_REVENUE_DIVERGENCE", lambda c, p: divergence("RECEIVABLES_REVENUE_DIVERGENCE", c, p), ar_rev, par_rev))
        
    inv_rev, pinv_rev = pair("inventory_revenue_ratio")
    out.append(_execute_signal("INVENTORY_SALES_DIVERGENCE", lambda c, p: divergence("INVENTORY_SALES_DIVERGENCE", c, p), inv_rev, pinv_rev))
        
    gm, pgm = pair("gross_margin")
    out.append(_execute_signal("GROSS_MARGIN_COMPRESSION", gross_margin_compression, gm, pgm))

    om, pom = pair("operating_margin")
    out.append(_execute_signal("OPERATING_MARGIN_DETERIORATION", operating_margin_deterioration, om, pom))

    fcf, pfcf = pair("free_cash_flow")
    out.append(_execute_signal("FREE_CASH_FLOW_DETERIORATION", fcf_deterioration, fcf, pfcf))

    conv, pconv = pair("cash_conversion")
    out.append(_execute_signal("EARNINGS_CASH_CONVERSION_DETERIORATION", cash_conversion, conv, pconv))

    lev, plev = pair("debt_operating_income")
    out.append(_execute_signal("DEBT_OPERATING_INCOME_DETERIORATION", leverage, lev, plev))

    liq, pliq = pair("liquidity_ratio")
    out.append(_execute_signal("LIQUIDITY_COMPRESSION", liquidity, liq, pliq))

    sh, psh = pair("share_count")
    out.append(_execute_signal("SHARE_COUNT_DILUTION", dilution, sh, psh))

    valid = [s for s in out if s is not None]
    valid.extend(cluster([s for s in valid if not s.suppressed_reason and s.severity in ('HIGH', 'MEDIUM', 'LOW')]))
    return valid




def deduplicate_observations(obs: list) -> list:
    from .models import DataQuality, QUALITY_RANK
    
    dedup = {}
    for o in obs:
        key = (o.company, o.metric, o.period_end, o.period_type, o.unit, getattr(o, 'period_start', None))
        if key not in dedup:
            dedup[key] = o
        else:
            existing = dedup[key]
            eq = QUALITY_RANK.get(existing.quality, 0)
            nq = QUALITY_RANK.get(o.quality, 0)
            if nq > eq:
                dedup[key] = o
    return list(dedup.values())

def ingest_company(client, c, company):
    """Full ingestion: SEC fetch -> normalize -> signals -> peers -> persist."""
    ticker = company["ticker"]
    cik = company["cik"]

    try:
        # Fetch from SEC
        sub = client.submissions(cik)
        facts = client.company_facts(cik)
        filings = filing_index(sub, cik)
    except Exception as e:
        # Persist failure signal but preserve previous data
        # Remove any previous INGESTION_FAILED signal, then add new one
        c.execute("DELETE FROM signals WHERE company=? AND signal_id='INGESTION_FAILED'", (ticker,))
        fail_sig = Signal(
            signal_id="INGESTION_FAILED",
            company=ticker,
            severity="HIGH",
            confidence="HIGH",
            explanation=f"SEC ingestion failed: {str(e)}",
            evidence=(),
        )
        save_signals(c, [fail_sig])
        raise

    # Normalize observations
    obs = extract_companyfacts(ticker, cik, facts, filings)
    
    # Derive Analytical Spine
    from .metrics import derive_analytical_metrics
    derived = derive_analytical_metrics(obs)
    obs.extend(derived)
    
    obs = deduplicate_observations(obs)
    
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
        key=lambda x: (x.get("filingDate", ""), x.get("accessionNumber", "")),
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
    required = ["ticker", "shares", "weight", "cost_basis", "exposure"]
    
    for req in required:
        if req not in df.columns:
            return False, f"CSV must contain '{req}' column."
            
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    
    if df["ticker"].duplicated().any():
        return False, "CSV contains duplicate tickers."
        
    for t in df["ticker"]:
        if t not in universe_tickers:
            return False, f"Ticker {t} is not in the 51-company universe."
            
    try:
        df["shares"] = df["shares"].astype(float)
        df["weight"] = df["weight"].astype(float)
        df["cost_basis"] = df["cost_basis"].astype(float)
        df["exposure"] = df["exposure"].astype(float)
    except ValueError:
        return False, "Numeric columns contain invalid non-numeric data."
        
    import numpy as np
    if df.isna().any().any() or np.isinf(df[["shares", "weight", "cost_basis", "exposure"]]).any().any():
        return False, "CSV contains NaN, infinity, or blank values."
        
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
    
    # Must have recent QUARTERLY evidence
    q_obs = [o for o in obs if o['period_type'] == 'QUARTER']
    if not q_obs:
        return ReadinessState.NOT_READY, "No quarterly observations found."
        
    max_q_end = max([o['period_end'] for o in q_obs])
    
    valid_metrics = set()
    for o in q_obs:
        if o['period_end'] == max_q_end and o['value'] is not None and o['quality'] in ('REPORTED', 'DERIVED', 'AMENDED', 'RESTATED') and o['comparable'] == 1 and o['provenance'] and o['provenance'] != "[]":
            valid_metrics.add(o['metric'])
            
    missing = core - valid_metrics
    if not missing:
        return ReadinessState.READY, "All core metrics successfully validated and comparable."
    elif len(valid_metrics) > 0:
        return ReadinessState.PARTIAL, f"Missing or invalid evidence for: {', '.join(missing)}"
    else:
        return ReadinessState.NOT_READY, "No valid comparable evidence found."
