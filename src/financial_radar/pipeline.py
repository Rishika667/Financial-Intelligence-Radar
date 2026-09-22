"""The single local production flow: SEC → raw → normalize → SQLite → signals/events."""
import json
from pathlib import Path
from .core import SECClient, free_cash_flow
from .normalization import extract_companyfacts
from .store import save_observations,save_watchlist,save_signals,save_events

from .signals import divergence,margin_compression,cluster
from .signals_phase2 import operating_deleverage,cash_conversion,fcf_deterioration,leverage,liquidity,dilution
from .events import extract_events
FORMS={"10-K","10-Q","8-K","20-F","6-K","10-K/A","10-Q/A"}
def load_universe(path="config/universe.json"):return json.loads(Path(path).read_text())["companies"]
def filing_index(submissions,cik):
 r=submissions.get("filings",{}).get("recent",{}); out={}
 for i,accession in enumerate(r.get("accessionNumber",[])):
  form=r.get("form",[None]*len(r["accessionNumber"]))[i]
  if form in FORMS:
   doc=r.get("primaryDocument",[""]*len(r["accessionNumber"]))[i]
   out[accession.replace("-","")]={"accessionNumber":accession,"form":form,"filingDate":r.get("filingDate",[None]*len(r["accessionNumber"]))[i],"source_url":f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-','')}/{doc}"}
 return out
def _latest(items,metric,pt):
 x=[o for o in items if o.metric==metric and o.period_type==pt and o.value is not None and o.comparable]
 return sorted(x,key=lambda o:o.period_end,reverse=True)
def evaluate(company,items):
 pt="QUARTER"; out=[]
 def pair(m):
  x=_latest(items,m,pt);return (x[0],x[1]) if len(x)>1 else (None,None)
 rev,prevrev=pair("revenue"); ar,prevar=pair("accounts_receivable"); inv,previnv=pair("inventory")
 if rev and prevrev and ar and prevar:out.append(divergence("RECEIVABLES_REVENUE_DIVERGENCE",ar,rev,prevar,prevrev))
 if rev and prevrev and inv and previnv:out.append(divergence("INVENTORY_SALES_DIVERGENCE",inv,rev,previnv,prevrev))
 gp,pgp=pair("gross_profit"); op,pop=pair("operating_income"); ni,pni=pair("net_income"); ocf,pocf=pair("operating_cash_flow"); debt,pdebt=pair("debt"); cash,pcash=pair("cash_and_equivalents"); cl,pcl=pair("current_liabilities"); shares,pshares=pair("share_count"); cap,pca=pair("capex")
 if gp and rev and pgp and prevrev: out.append(margin_compression(_ratio(gp,rev,"gross_margin"),_ratio(pgp,prevrev,"gross_margin")))
 if op and rev and pop and prevrev: out.append(operating_deleverage(_ratio(op,rev,"operating_margin"),_ratio(pop,prevrev,"operating_margin")))
 if ocf and ni and pocf and pni:out.append(cash_conversion(ocf,ni,pocf,pni))
 if ocf and cap and pocf and pca:out.append(fcf_deterioration(free_cash_flow(ocf,cap),free_cash_flow(pocf,pca)))
 if debt and op and pdebt and pop:out.append(leverage(debt,op,pdebt,pop))
 if cash and cl and pcash and pcl:out.append(liquidity(cash,cl,pcash,pcl))
 if shares and pshares:out.append(dilution(shares,pshares))
 out=[x for x in out if x];return out+cluster(out)
def _ratio(a,b,name):
 from .models import Observation,DataQuality
 if b.value in (None,0):return Observation(a.company,name,None,"ratio",a.period_end,a.period_type,DataQuality.CALCULATION_INVALID,comparable=False)
 return Observation(a.company,name,a.value/b.value,"ratio",a.period_end,a.period_type,DataQuality.DERIVED,a.provenance+b.provenance)
def ingest_company(client,c,company):
 sub=client.submissions(company["cik"]); facts=client.company_facts(company["cik"]); obs=extract_companyfacts(company["ticker"],company["cik"],facts,filing_index(sub,company["cik"])); save_observations(c,obs); sig=evaluate(company["ticker"],obs); save_signals(c,sig); return {"observations":len(obs),"signals":len(sig)}
def ingest_events(company,filing,text,c):save_events(c,extract_events(company["ticker"],filing,text))