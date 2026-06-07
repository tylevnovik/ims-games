import sqlite3

conn = sqlite3.connect(r"C:\Users\blmpt\PycharmProjects\CWSS\data\db\ims_games.sqlite")
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("=== TABLES ===")
for t in tables:
    print(f"\n--- {t[0]} ---")
    cur.execute(f"PRAGMA table_info([{t[0]}])")
    for col in cur.fetchall():
        print(f"  {col}")

# Sample rows from key tables
for tbl in ["game_identity", "reviews", "platforms"]:
    try:
        cur.execute(f"SELECT * FROM [{tbl}] LIMIT 3")
        rows = cur.fetchall()
        print(f"\n=== SAMPLE {tbl} ===")
        for r in rows:
            print(r)
    except Exception as e:
        print(f"\n=== {tbl}: {e} ===")

conn.close()
