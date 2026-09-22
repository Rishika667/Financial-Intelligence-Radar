import re,hashlib
PATTERNS={"acquisition":r"\b(acquisition|merger)\b","divestiture":r"\b(divestiture|dispose)\b","debt":r"\b(refinanc|credit facility|notes due)\b","equity":r"\b(equity offering|stock issuance)\b","buyback":r"\b(repurchase|buyback)\b","restructuring":r"\brestructur","material_agreement":r"material definitive agreement","legal":r"\b(litigation|lawsuit)\b","segment":r"\bsegment change"}
def extract_events(company,filing,text):
 out=[]
 for typ,p in PATTERNS.items():
  m=re.search(p,text,re.I)
  if m:out.append({"id":hashlib.sha1(f"{company}{filing.get('accessionNumber')}{typ}".encode()).hexdigest()[:16],"company":company,"type":typ,"filing_date":filing.get("filingDate"),"accession":filing.get("accessionNumber"),"source_url":filing.get("source_url"),"description":text[max(0,m.start()-100):m.end()+200].replace("\n"," ")})
 return out