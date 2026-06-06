"""Backfill review platform field from game-level platform data (enriched from RAWG).

Uses a single efficient UPDATE ... FROM instead of per-game queries.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH


def backfill_platforms():
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    t0 = time.time()

    # Step 1: Build game_id -> primary_platform mapping in Python
    print("Loading game platform data...")
    game_platforms = {}
    for row in conn.execute(
        "SELECT game_id, platforms FROM games WHERE platforms IS NOT NULL"
    ):
        try:
            plats = json.loads(row[1])
            if plats and isinstance(plats, list) and isinstance(plats[0], str):
                game_platforms[row[0]] = plats[0]
        except (json.JSONDecodeError, TypeError, IndexError):
            pass
    print(f"  Games with platform: {len(game_platforms):,}")

    # Step 2: Create a temp table for fast lookup
    print("Creating temp mapping table...")
    conn.execute("DROP TABLE IF EXISTS _platform_map")
    conn.execute("CREATE TEMP TABLE _platform_map (game_id TEXT PRIMARY KEY, platform TEXT)")
    conn.executemany(
        "INSERT INTO _platform_map (game_id, platform) VALUES (?, ?)",
        list(game_platforms.items()),
    )
    conn.commit()
    print(f"  Inserted {len(game_platforms):,} mappings")

    # Step 3: Single bulk UPDATE
    print("Running bulk UPDATE...")
    cursor = conn.execute("""
        UPDATE reviews
        SET platform = (
            SELECT pm.platform FROM _platform_map pm WHERE pm.game_id = reviews.game_id
        )
        WHERE reviews.platform IS NULL
          AND reviews.game_id IN (SELECT game_id FROM _platform_map)
    """)
    conn.commit()
    updated = cursor.rowcount
    elapsed_update = time.time() - t0
    print(f"  Updated {updated:,} reviews in {elapsed_update:.1f}s")

    # Step 4: Cleanup
    conn.execute("DROP TABLE IF EXISTS _platform_map")
    conn.commit()

    # Step 5: Verify
    filled = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE platform IS NOT NULL"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    print(f"\nResult: {filled:,}/{total:,} reviews now have platform ({100 * filled / total:.1f}%)")

    print("\n=== Platform distribution (top 15) ===")
    for row in conn.execute(
        "SELECT platform, COUNT(*) as c FROM reviews WHERE platform IS NOT NULL GROUP BY platform ORDER BY c DESC LIMIT 15"
    ):
        print(f"  {row[0]:20s} {row[1]:>8,}")

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")
    conn.close()


if __name__ == "__main__":
    backfill_platforms()
