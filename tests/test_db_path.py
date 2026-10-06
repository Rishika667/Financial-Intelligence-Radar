import pytest
import sqlite3
import os

def test_db_path():
    db = sqlite3.connect("test_research_radar.db")
    print(db.execute("SELECT * FROM watchlist").fetchall())
