from .models import Signal,DataQuality
from .core import pct_change
def ok(*x):return all(a and a.value is not None and a.comparable and a.quality in (DataQuality.REPORTED,DataQuality.DERIVED,DataQuality.AMENDED) for a in x)
def suppressed(id,*x):return Signal(id,x[0].company,"","LOW","Suppressed: unreliable or incomparable evidence",x,suppressed_reason="data quality/comparability")
def decline(id,current,prior,floor,label):
 if not ok(current,prior):return suppressed(id,current,prior)
 d=current.value-prior.value
 return Signal(id,current.company,"HIGH" if d<=-2*floor else "MODERATE","HIGH",f"{label} deteriorated by {abs(d):.2f}.",(current,prior)) if d<=-floor else None
def operating_deleverage(c,p):return decline("OPERATING_DELEVERAGE",c,p,.03,"Operating margin")
def fcf_deterioration(c,p):return decline("FREE_CASH_FLOW_DETERIORATION",c,p,max(abs(p.value)*.2,1) if p.value is not None else 1,"Free cash flow")
def dilution(c,p):
 if not ok(c,p):return suppressed("SHARE_COUNT_DILUTION",c,p)
 r=pct_change(c.value,p.value);return Signal("SHARE_COUNT_DILUTION",c.company,"HIGH" if r>=.1 else "MODERATE","HIGH",f"Share count increased {r:.1%}.",(c,p)) if r is not None and r>=.03 else None
def ratio_drop(id,a,b,oa,ob,floor,label):
 if not ok(a,b,oa,ob) or b.value<=0 or ob.value<=0:return suppressed(id,a,b)
 now,old=a.value/b.value,oa.value/ob.value
 return Signal(id,a.company,"HIGH" if old-now>=2*floor else "MODERATE","HIGH",f"{label} declined from {old:.2f}x to {now:.2f}x.",(a,b,oa,ob)) if old-now>=floor else None
def cash_conversion(a,b,oa,ob):return ratio_drop("EARNINGS_CASH_CONVERSION_DETERIORATION",a,b,oa,ob,.2,"OCF/earnings conversion")
def liquidity(a,b,oa,ob):return ratio_drop("LIQUIDITY_COMPRESSION",a,b,oa,ob,.1,"Cash/current-liabilities")
def leverage(a,b,oa,ob):return ratio_drop("LEVERAGE_INTEREST_BURDEN",oa,ob,a,b,.5,"Debt/operating-income")