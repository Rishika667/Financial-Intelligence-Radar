from datetime import date,datetime
from financial_radar.models import Observation,Provenance,DataQuality
from financial_radar.pipeline import evaluate
from financial_radar.normalization import extract_companyfacts
def o(metric,value,end,provenance=()):
 return Observation("ABC",metric,value,"USD",end,"QUARTER",DataQuality.REPORTED,provenance)
def test_pipeline_signal_keeps_provenance():
 p=Provenance("0001","https://sec.example/f","2025-01-01" if False else date(2025,1,1),"10-Q","RevenueFromContractWithCustomerExcludingAssessedTax",datetime(2025,1,2),100)
 now=date(2025,6,30); old=date(2024,6,30)
 data=[o("revenue",100,now,(p,)),o("revenue",100,old,(p,)),o("accounts_receivable",150,now,(p,)),o("accounts_receivable",100,old,(p,))]
 signals=evaluate("ABC",data); hit=next(s for s in signals if s.signal_id=="RECEIVABLES_REVENUE_DIVERGENCE")
 assert hit.evidence[0].provenance[0].accession=="0001"
def test_normalization_missing_is_not_zero():
 payload={"facts":{"us-gaap":{"RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":[{"accn":"0001","filed":"2025-01-01","form":"10-Q","end":"2024-12-31","start":"2024-10-01","fp":"Q1","val":10}]}}}}}
 rows=extract_companyfacts("ABC","1",payload,{"0001":{"source_url":"https://sec.example","accessionNumber":"0001"}})
 revenue=next(x for x in rows if x.metric=="revenue"); inventory=next(x for x in rows if x.metric=="inventory")
 assert revenue.value==10 and inventory.value is None and inventory.quality==DataQuality.NOT_REPORTED