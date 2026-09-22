from datetime import date
from financial_radar.models import Observation,DataQuality
from financial_radar.signals_phase2 import *
def o(m,v):return Observation("ABC",m,v,"USD",date(2025,6,30),"QUARTER",DataQuality.REPORTED)
def test_new_signals():
 assert operating_deleverage(o("margin",.1),o("margin",.2))
 assert fcf_deterioration(o("fcf",50),o("fcf",100))
 assert dilution(o("shares",110),o("shares",100))
 assert cash_conversion(o("ocf",40),o("ni",100),o("ocf",100),o("ni",100))
 assert liquidity(o("cash",10),o("cl",100),o("cash",50),o("cl",100))
 assert leverage(o("debt",300),o("ebit",100),o("debt",100),o("ebit",100))