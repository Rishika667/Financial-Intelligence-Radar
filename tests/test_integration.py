from datetime import date,datetime
from financial_radar.models import Observation,Provenance,DataQuality
from financial_radar.store import connect,save_watchlist,save_observations,rows
from financial_radar.signals_phase2 import leverage
from financial_radar.events import extract_events
def o(m,v):return Observation("ABC",m,v,"USD",date(2025,6,30),"QUARTER",DataQuality.REPORTED)
def test_store_and_watchlist(tmp_path):
 c=connect(tmp_path/"x.sqlite");save_watchlist(c,[{"ticker":"ABC","cik":"1","active":True}]);save_observations(c,[o("revenue",2)]);assert rows(c,"select * from watchlist")[0]["ticker"]=="ABC";assert rows(c,"select * from observations")[0]["value"]==2
def test_leverage_direction_and_event():
 assert leverage(o("debt",300),o("ebit",100),o("debt",100),o("ebit",100))
 assert extract_events("ABC",{"accessionNumber":"x","filingDate":"2025-01-01","source_url":"s"},"The company completed an acquisition.")