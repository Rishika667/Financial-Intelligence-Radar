from datetime import date,datetime
from .models import Observation,Provenance,DataQuality
CONCEPTS={"revenue":("RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","Revenues"),"gross_profit":("GrossProfit",),"operating_income":("OperatingIncomeLoss",),"net_income":("NetIncomeLoss",),"operating_cash_flow":("NetCashProvidedByUsedInOperatingActivities",),"capex":("PaymentsToAcquirePropertyPlantAndEquipment",),"accounts_receivable":("AccountsReceivableNetCurrent",),"inventory":("InventoryNet",),"cash_and_equivalents":("CashAndCashEquivalentsAtCarryingValue",),"current_liabilities":("LiabilitiesCurrent",),"debt":("LongTermDebtCurrent","LongTermDebtNoncurrent"),"share_count":("WeightedAverageNumberOfDilutedSharesOutstanding",)}
def extract_companyfacts(company,cik,payload,filings):
 out=[]
 for metric,tags in CONCEPTS.items():
  found=False
  for tax,nodes in payload.get("facts",{}).items():
   for tag in tags:
    for unit,items in nodes.get(tag,{}).get("units",{}).items():
     for x in items:
      acc=x.get("accn","").replace("-",""); filing=filings.get(acc,{})
      prov=Provenance(acc,filing.get("source_url",""),date.fromisoformat(x["filed"]),x.get("form",""),tag,datetime.utcnow(),x.get("val"))
      pt="INSTANT" if not x.get("start") else ("ANNUAL" if x.get("fp")=="FY" else "YTD" if x.get("fp") in ("Q2","Q3") else "QUARTER")
      q=DataQuality.AMENDED if str(x.get("form","")).endswith("/A") else DataQuality.REPORTED
      out.append(Observation(company,metric,x.get("val"),unit,date.fromisoformat(x["end"]),pt,q,(prov,))); found=True
  if not found: out.append(Observation(company,metric,None,"USD",date.today(),"UNKNOWN",DataQuality.NOT_REPORTED,comparable=False,comparability_reason="No accepted standard XBRL concept"))
 return out