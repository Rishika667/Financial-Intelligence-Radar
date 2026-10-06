import sqlite3
c = sqlite3.connect("test_radar.db")
c.row_factory = sqlite3.Row
print([dict(r) for r in c.execute("SELECT * FROM watchlist").fetchall()])
