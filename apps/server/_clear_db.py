import sqlite3
from pathlib import Path

p = Path(__file__).resolve().parent / "data" / "platform.db"
con = sqlite3.connect(p)
cur = con.cursor()
tables = [
    r[0]
    for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1"
    ).fetchall()
]
print("tables:", tables)
for t in tables:
    n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    print(f"  {t}: {n}")
for t in tables:
    cur.execute(f'DELETE FROM "{t}"')
con.commit()
print("--- after ---")
for t in tables:
    n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    print(f"  {t}: {n}")
con.close()
print("cleared", p)
