"""Enrich IMS Games database with metadata from RAWG dataset.

Matches games by:
  1. Slug (game_identity.external_slug == RAWG slug) — most reliable
  2. Metacritic URL slug (extracted from RAWG metacritic_url)
  3. Normalized title + release year — fallback

Updates games table fields:
  - developer, publisher, genres, platforms, description

Also inserts external_baseline records for OpenCritic-style metacritic scores
from RAWG (source_platform = 'rawg_metacritic').
"""

import json
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH

RAWG_PATH = Path(__file__).parent.parent / "data" / "rawg" / "rawg_data.jsonl"


# ---------------------------------------------------------------------------
# Text normalization for matching
# ---------------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """Normalize a game title for fuzzy matching."""
    if not title:
        return ""
    # NFD normalize, strip combining chars (accents)
    t = unicodedata.normalize("NFD", title)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    # Lowercase, strip punctuation except spaces
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_mc_slug(metacritic_url: str) -> str:
    """Extract the game slug from a metacritic URL.

    Example: https://www.metacritic.com/game/playstation-4/the-witcher-3-wild-hunt
             -> the-witcher-3-wild-hunt
    """
    if not metacritic_url:
        return ""
    # URL pattern: /game/{platform}/{slug}
    m = re.search(r"/game/[^/]+/([^/?#]+)", metacritic_url)
    return m.group(1) if m else ""


def extract_names(items: list | None) -> str | None:
    """Extract comma-separated names from RAWG nested dicts."""
    if not items:
        return None
    names = []
    for item in items:
        if isinstance(item, dict) and "name" in item:
            names.append(item["name"])
        elif isinstance(item, dict) and "platform" in item:
            p = item["platform"]
            if isinstance(p, dict) and "name" in p:
                names.append(p["name"])
    return ", ".join(names) if names else None


def extract_platform_names(items: list | None) -> list[str]:
    """Extract platform names from RAWG parent_platforms."""
    if not items:
        return []
    names = []
    for item in items:
        if isinstance(item, dict) and "platform" in item:
            p = item["platform"]
            if isinstance(p, dict) and "name" in p:
                names.append(p["name"])
    return names


def extract_genre_names(items: list | None) -> list[str]:
    """Extract genre names from RAWG genres."""
    if not items:
        return []
    return [x["name"] for x in items if isinstance(x, dict) and "name" in x]


# ---------------------------------------------------------------------------
# Build indices from database
# ---------------------------------------------------------------------------

def build_db_indices(conn):
    """Build lookup dictionaries from the IMS database."""
    print("Building database indices...")

    # Slug -> game_id (from game_identity)
    slug_to_gid = {}
    for row in conn.execute(
        "SELECT external_slug, game_id FROM game_identity WHERE external_slug IS NOT NULL"
    ):
        slug = row[0].strip().lower()
        if slug:
            slug_to_gid[slug] = row[1]

    # MC URL slug -> game_id (also from game_identity, for metacritic URLs)
    # The external_slug from metacritic_kaggle is already the MC slug format

    # Title+year -> game_id
    title_year_to_gid = {}
    title_to_gid = {}
    for row in conn.execute("SELECT game_id, title, release_year FROM games"):
        gid, title, year = row
        if title:
            nt = normalize_title(title)
            if nt:
                title_to_gid[nt] = gid
                if year:
                    title_year_to_gid[(nt, year)] = gid

    print(f"  Slug index: {len(slug_to_gid):,} entries")
    print(f"  Title+year index: {len(title_year_to_gid):,} entries")
    print(f"  Title-only index: {len(title_to_gid):,} entries")

    return slug_to_gid, title_year_to_gid, title_to_gid


# ---------------------------------------------------------------------------
# Main enrichment
# ---------------------------------------------------------------------------

def enrich():
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        sys.exit(1)
    if not RAWG_PATH.exists():
        print(f"[ERROR] RAWG data not found: {RAWG_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    slug_to_gid, title_year_to_gid, title_to_gid = build_db_indices(conn)

    # Track what's already enriched (avoid overwriting good data)
    existing_data = {}
    for row in conn.execute(
        "SELECT game_id, developer, publisher, genres, platforms, description FROM games"
    ):
        existing_data[row[0]] = {
            "developer": row[1],
            "publisher": row[2],
            "genres": row[3],
            "platforms": row[4],
            "description": row[5],
        }

    # Collect updates
    updates = []       # (developer, publisher, genres, platforms, description, game_id)
    mc_baselines = []  # external_baseline entries from RAWG metacritic scores
    matched_gids = set()
    match_stats = {"slug": 0, "mc_url": 0, "title_year": 0, "title": 0, "skipped": 0}

    print(f"\nScanning RAWG data ({RAWG_PATH})...")
    t0 = time.time()
    scanned = 0

    with open(RAWG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            scanned += 1
            if scanned % 100000 == 0:
                elapsed = time.time() - t0
                print(f"  Scanned {scanned:,} records ({len(matched_gids):,} matched) [{elapsed:.0f}s]")

            d = json.loads(line)
            rawg_slug = d.get("slug", "")
            rawg_name = d.get("name", "")
            rawg_year = None
            released = d.get("released")
            if released:
                try:
                    rawg_year = int(released[:4])
                except (ValueError, TypeError):
                    pass

            # --- Match ---
            game_id = None
            match_method = None

            # Method 1: Direct slug match
            if rawg_slug and rawg_slug in slug_to_gid:
                game_id = slug_to_gid[rawg_slug]
                match_method = "slug"

            # Method 2: Metacritic URL slug match
            if not game_id:
                mc_url = d.get("metacritic_url", "")
                mc_slug = extract_mc_slug(mc_url)
                if mc_slug and mc_slug in slug_to_gid:
                    game_id = slug_to_gid[mc_slug]
                    match_method = "mc_url"

            # Method 3: Title + year match
            if not game_id and rawg_name:
                nt = normalize_title(rawg_name)
                if nt and rawg_year:
                    key = (nt, rawg_year)
                    if key in title_year_to_gid:
                        game_id = title_year_to_gid[key]
                        match_method = "title_year"

            # Method 4: Title-only match (less reliable, but still useful)
            if not game_id and rawg_name:
                nt = normalize_title(rawg_name)
                if nt and nt in title_to_gid:
                    game_id = title_to_gid[nt]
                    match_method = "title"

            # Skip if no match or already processed
            if not game_id or game_id in matched_gids:
                if game_id:
                    match_stats["skipped"] += 1
                continue

            # Check if this game already has data
            existing = existing_data.get(game_id, {})
            has_all = all(existing.get(f) for f in ["developer", "genres", "platforms"])
            if has_all:
                match_stats["skipped"] += 1
                continue

            matched_gids.add(game_id)
            match_stats[match_method] += 1

            # --- Extract fields ---
            developer = extract_names(d.get("developers"))
            publisher = extract_names(d.get("publishers"))
            genres = extract_genre_names(d.get("genres"))
            platforms = extract_platform_names(d.get("parent_platforms"))
            description = d.get("description_raw") or None
            mc_score = d.get("metacritic")

            # Build update tuple (only overwrite null fields)
            upd_dev = developer if not existing.get("developer") else existing["developer"]
            upd_pub = publisher if not existing.get("publisher") else existing["publisher"]
            upd_genres = json.dumps(genres, ensure_ascii=False) if (not existing.get("genres") and genres) else existing.get("genres")
            upd_platforms = json.dumps(platforms, ensure_ascii=False) if (not existing.get("platforms") and platforms) else existing.get("platforms")
            upd_desc = description if not existing.get("description") else existing["description"]

            updates.append((upd_dev, upd_pub, upd_genres, upd_platforms, upd_desc, game_id))

            # External baseline (RAWG metacritic score)
            if mc_score is not None:
                import hashlib
                bl_id = "rawg-bl-" + hashlib.md5(game_id.encode()).hexdigest()[:16]
                mc_baselines.append({
                    "baseline_id": bl_id,
                    "game_id": game_id,
                    "target_id": None,
                    "source_platform": "rawg_metacritic",
                    "external_score": float(mc_score),
                    "external_user_score": None,
                    "review_count": None,
                    "user_review_count": None,
                    "source_url": d.get("metacritic_url"),
                    "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    "data_source": "rawg_enrichment",
                    "license_note": "RAWG.io free dataset",
                })

    elapsed = time.time() - t0
    print(f"\nScan complete: {scanned:,} records in {elapsed:.1f}s")
    print(f"\nMatch stats:")
    for method, count in match_stats.items():
        print(f"  {method:15s}: {count:,}")
    print(f"  Total matched: {len(matched_gids):,}")

    # --- Apply updates ---
    if updates:
        print(f"\nUpdating {len(updates):,} games...")
        conn.executemany(
            """UPDATE games SET
                developer = ?, publisher = ?, genres = ?, platforms = ?, description = ?
            WHERE game_id = ?""",
            updates,
        )
        conn.commit()
        print(f"  Updated {len(updates):,} games.")

    # --- Insert external baselines ---
    if mc_baselines:
        print(f"\nInserting {len(mc_baselines):,} RAWG metacritic baselines...")
        # Clear old rawg baselines first
        conn.execute("DELETE FROM external_baseline WHERE data_source = 'rawg_enrichment'")
        cols = list(mc_baselines[0].keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        col_names = ", ".join(cols)
        conn.executemany(
            f"INSERT INTO external_baseline ({col_names}) VALUES ({placeholders})",
            mc_baselines,
        )
        conn.commit()
        print(f"  Inserted {len(mc_baselines):,} baselines.")

    # --- Verification ---
    print("\n=== Verification ===")
    total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    for col in ["developer", "publisher", "genres", "platforms", "description"]:
        filled = conn.execute(
            f"SELECT COUNT(*) FROM games WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchone()[0]
        print(f"  {col:15s}: {filled:,}/{total:,} ({100 * filled / total:.1f}%)")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    enrich()
