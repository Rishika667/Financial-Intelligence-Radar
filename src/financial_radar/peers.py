from statistics import median
def peer_context(company,metric,observations,members):
 values=[o.value for o in observations if o.company in members and o.metric==metric and o.value is not None and o.comparable]
 own=[o.value for o in observations if o.company==company and o.metric==metric and o.value is not None]
 return {"available":len(values)>=2 and bool(own),"company":own[-1] if own else None,"peer_median":median(values) if len(values)>=2 else None,"peer_range":(min(values),max(values)) if values else None,"n":len(values)}