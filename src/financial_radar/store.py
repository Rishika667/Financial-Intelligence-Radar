import json,sqlite3
from pathlib import Path
DDL="CREATE TABLE IF NOT EXISTS watchlist(ticker TEXT PRIMARY KEY,cik TEXT,active INTEGER,metadata TEXT);CREATE TABLE IF NOT EXISTS observations(company TEXT,metric TEXT,value REAL,unit TEXT,period_end TEXT,period_type TEXT,quality TEXT,comparable INTEGER,reason TEXT,provenance TEXT);CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,company TEXT,type TEXT,filed TEXT,accession TEXT,source_url TEXT,description TEXT);"
def connect(path="data/radar.sqlite"):Path(path).parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(path);c.executescript(DDL);return c
def save_watchlist(c,rows):
 for x in rows:c.execute("INSERT OR REPLACE INTO watchlist VALUES(?,?,?,?)",(x["ticker"],x["cik"],int(x.get("active",True)),json.dumps(x)))
 c.commit()
def save_observations(c,rows):
 for o in rows:c.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?)",(o.company,o.metric,o.value,o.unit,o.period_end.isoformat(),o.period_type,o.quality.value,int(o.comparable),o.comparability_reason,json.dumps([p.__dict__ for p in o.provenance],default=str)))
 c.commit()