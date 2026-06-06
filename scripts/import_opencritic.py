"""Import OpenCritic review data (or generate mock data) into the IMS Games database.

Modes:
    - API mode:  if OPENCRITIC_API_KEY env var is set, fetch from API (placeholder)
    - Mock mode: generate realistic mock review data for ~25 popular games already
                  present in the database (from a prior Metacritic import)

Usage:
    python import_opencritic.py
"""

import hashlib
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import (
    ALGORITHM_VERSION,
    DB_URL,
    OPENCRITIC_API_KEY,
    OPENCRITIC_DIR,
    ensure_dirs,
)


# ---------------------------------------------------------------------------
# Deterministic ID helpers (same scheme as other importers)
# ---------------------------------------------------------------------------


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def game_id_for(title: str) -> str:
    return f"mc-{_md5(title)[:16]}"


def oc_source_id_for(name: str) -> str:
    return f"oc-src-{_md5(name)[:12]}"


def oc_review_id_for(game_title: str, source_name: str) -> str:
    return f"oc-rev-{_md5(game_title + '||' + source_name)[:16]}"


def oc_identity_id_for(title: str) -> str:
    return f"oc-id-{_md5(title)[:16]}"


def oc_target_id_for(title: str) -> str:
    return f"oc-tgt-{_md5(title)[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Well-known games to try to match in the DB
# ---------------------------------------------------------------------------

# A curated list of popular, well-known games. We will check which of these
# exist in the database (imported from Metacritic) and pick up to 25.
WELL_KNOWN_GAMES = [
    "The Legend of Zelda: Breath of the Wild",
    "The Legend of Zelda: Ocarina of Time",
    "The Legend of Zelda: Tears of the Kingdom",
    "Super Mario Odyssey",
    "Super Mario Galaxy",
    "Super Smash Bros. Ultimate",
    "Red Dead Redemption 2",
    "Grand Theft Auto V",
    "The Witcher 3: Wild Hunt",
    "Elden Ring",
    "Dark Souls III",
    "God of War",
    "God of War Ragnarok",
    "The Last of Us",
    "The Last of Us Part II",
    "Uncharted 4: A Thief's End",
    "Horizon Zero Dawn",
    "Ghost of Tsushima",
    "Persona 5",
    "Final Fantasy VII Remake",
    "Hades",
    "Hollow Knight",
    "Celeste",
    "Undertale",
    "Stardew Valley",
    "Minecraft",
    "Portal 2",
    "Mass Effect 2",
    "BioShock",
    "Half-Life 2",
    "Overwatch",
    "Doom",
    "Resident Evil Village",
    "Animal Crossing: New Horizons",
    "Pokemon Scarlet",
    "Pokemon Violet",
    "Splatoon 3",
    "Kirby and the Forgotten Land",
    "Detroit: Become Human",
    "Days Gone",
    "Final Fantasy XV",
]

# Approximate "quality tier" for each game (used to generate realistic scores)
# Higher = better game. On a rough 50-100 scale.
GAME_QUALITY = {
    "The Legend of Zelda: Breath of the Wild": 96,
    "The Legend of Zelda: Ocarina of Time": 97,
    "The Legend of Zelda: Tears of the Kingdom": 95,
    "Super Mario Odyssey": 94,
    "Super Mario Galaxy": 95,
    "Super Smash Bros. Ultimate": 92,
    "Red Dead Redemption 2": 95,
    "Grand Theft Auto V": 93,
    "The Witcher 3: Wild Hunt": 93,
    "Elden Ring": 94,
    "Dark Souls III": 88,
    "God of War": 93,
    "God of War Ragnarok": 92,
    "The Last of Us": 94,
    "The Last of Us Part II": 90,
    "Uncharted 4: A Thief's End": 92,
    "Horizon Zero Dawn": 88,
    "Ghost of Tsushima": 85,
    "Persona 5": 92,
    "Final Fantasy VII Remake": 87,
    "Hades": 91,
    "Hollow Knight": 89,
    "Celeste": 90,
    "Undertale": 88,
    "Stardew Valley": 87,
    "Minecraft": 90,
    "Portal 2": 93,
    "Mass Effect 2": 94,
    "BioShock": 93,
    "Half-Life 2": 95,
    "Overwatch": 88,
    "Doom": 85,
    "Resident Evil Village": 83,
    "Animal Crossing: New Horizons": 88,
    "Pokemon Scarlet": 72,
    "Pokemon Violet": 72,
    "Splatoon 3": 83,
    "Kirby and the Forgotten Land": 84,
    "Detroit: Become Human": 78,
    "Days Gone": 71,
    "Final Fantasy XV": 77,
}

# Mock media sources (major gaming outlets)
MOCK_SOURCES = [
    {"name": "IGN", "bias": 0, "variance": 4, "language": "en", "region": "US"},
    {"name": "GameSpot", "bias": -1, "variance": 5, "language": "en", "region": "US"},
    {"name": "Polygon", "bias": -2, "variance": 6, "language": "en", "region": "US"},
    {"name": "Eurogamer", "bias": 1, "variance": 4, "language": "en", "region": "EU"},
    {"name": "Kotaku", "bias": -1, "variance": 7, "language": "en", "region": "US"},
    {"name": "Destructoid", "bias": 0, "variance": 5, "language": "en", "region": "US"},
    {"name": "Game Informer", "bias": 1, "variance": 4, "language": "en", "region": "US"},
    {"name": "The Guardian", "bias": -1, "variance": 5, "language": "en", "region": "UK"},
    {"name": "VG247", "bias": -2, "variance": 6, "language": "en", "region": "UK"},
    {"name": "Push Square", "bias": 0, "variance": 5, "language": "en", "region": "UK"},
    {"name": "Nintendo Life", "bias": 2, "variance": 4, "language": "en", "region": "UK"},
    {"name": "PC Gamer", "bias": 0, "variance": 5, "language": "en", "region": "US"},
    {"name": "GamesRadar+", "bias": -1, "variance": 5, "language": "en", "region": "UK"},
    {"name": "Shacknews", "bias": -1, "variance": 6, "language": "en", "region": "US"},
    {"name": "VGC", "bias": 0, "variance": 5, "language": "en", "region": "UK"},
]


# ---------------------------------------------------------------------------
# Mock review generation
# ---------------------------------------------------------------------------


def _generate_score(base_quality: int, source_info: dict, rng: random.Random) -> float:
    """Generate a realistic review score given a base quality and source bias."""
    bias = source_info["bias"]
    variance = source_info["variance"]
    raw = base_quality + bias + rng.gauss(0, variance)
    # Clamp to 0-100 and round to nearest integer (most outlets use whole numbers)
    return float(max(0, min(100, round(raw))))


def _generate_review_date(base_year: int, rng: random.Random) -> str:
    """Generate a plausible review date near the game's release."""
    base = datetime(base_year, 6, 1)
    offset = timedelta(days=rng.randint(-30, 60))
    return (base + offset).strftime("%Y-%m-%d")


def _generate_review_url(source_name: str, game_slug: str) -> str:
    slug = source_name.lower().replace(" ", "-").replace("+", "plus")
    return f"https://{slug}.com/review/{game_slug}"


# ---------------------------------------------------------------------------
# API mode (placeholder)
# ---------------------------------------------------------------------------


def fetch_from_api() -> list[dict]:
    """Placeholder: fetch game data from OpenCritic API.

    A real implementation would:
    1. Query the OpenCritic API for top games
    2. Fetch reviews for each game
    3. Return structured data
    """
    print("[opencritic] API mode is a placeholder. No real API calls made.")
    print("[opencritic] Returning empty result set.")
    return []


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------


def find_matched_games(session) -> list[str]:
    """Find well-known games that already exist in the database."""
    # Get all game titles currently in the DB
    result = session.execute(text("SELECT game_id, title FROM games"))
    db_games = {row[1]: row[0] for row in result}

    matched = []
    for title in WELL_KNOWN_GAMES:
        if title in db_games:
            matched.append(title)
        if len(matched) >= 25:
            break

    return matched


def generate_mock_data(matched_games: list[str]) -> dict:
    """Generate mock OpenCritic-style review data for matched games.

    Returns a dict with keys: sources, reviews, identities
    """
    # Use a fixed seed for deterministic output
    rng = random.Random(42)

    # Select a subset of sources for each game (3-8 per game)
    all_source_names = [s["name"] for s in MOCK_SOURCES]
    source_info_map = {s["name"]: s for s in MOCK_SOURCES}

    reviews = []
    now = _now()

    for game_title in matched_games:
        quality = GAME_QUALITY.get(game_title, 80)
        game_slug = game_title.lower().replace(" ", "-").replace(":", "").replace("'", "")

        # Pick 3-8 random sources for this game
        num_sources = rng.randint(3, 8)
        chosen_sources = rng.sample(all_source_names, min(num_sources, len(all_source_names)))

        # Estimate release year from DB game or default
        base_year = 2020  # default fallback

        for src_name in chosen_sources:
            src_info = source_info_map[src_name]
            score = _generate_score(quality, src_info, rng)
            review_date = _generate_review_date(base_year, rng)
            review_url = _generate_review_url(src_name, game_slug)

            reviews.append({
                "game_title": game_title,
                "game_id": game_id_for(game_title),
                "source_name": src_name,
                "source_id": oc_source_id_for(src_name),
                "review_id": oc_review_id_for(game_title, src_name),
                "score": score,
                "review_date": review_date,
                "review_url": review_url,
                "language": src_info["language"],
                "region": src_info["region"],
            })

    # Build identity entries for each matched game
    identities = []
    for title in matched_games:
        slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "")
        identities.append({
            "identity_id": oc_identity_id_for(title),
            "game_id": game_id_for(title),
            "source_name": "opencritic_mock",
            "external_id": None,
            "external_slug": slug,
            "external_title": title,
            "external_url": f"https://opencritic.com/game/{slug}",
            "match_confidence": 0.95,
            "match_method": "title_similarity",
            "needs_manual_review": 0,
            "created_at": now,
            "updated_at": now,
        })

    return {
        "sources": MOCK_SOURCES,
        "reviews": reviews,
        "identities": identities,
    }


# ---------------------------------------------------------------------------
# Database write helpers
# ---------------------------------------------------------------------------


def _upsert_dicts(session, table_name: str, rows: list[dict]) -> None:
    """INSERT OR REPLACE for idempotency."""
    if not rows:
        return
    columns = list(rows[0].keys())
    cols_sql = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = f"INSERT OR REPLACE INTO {table_name} ({cols_sql}) VALUES ({placeholders})"
    session.execute(text(sql), rows)
    session.commit()


def _insert_dicts(session, table_name: str, rows: list[dict]) -> None:
    """Plain INSERT (used when data was already cleared)."""
    if not rows:
        return
    columns = list(rows[0].keys())
    cols_sql = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders})"
    session.execute(text(sql), rows)
    session.commit()


# ---------------------------------------------------------------------------
# Main import flow
# ---------------------------------------------------------------------------


def run_import() -> None:
    ensure_dirs()
    now = _now()

    engine = create_engine(DB_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Decide mode
        api_key = OPENCRITIC_API_KEY
        use_api = bool(api_key)

        if use_api:
            print("[opencritic] OPENCRITIC_API_KEY found. Attempting API mode...")
            api_data = fetch_from_api()
            if not api_data:
                print("[opencritic] API returned no data. Falling back to mock mode.")
                use_api = False
        else:
            print("[opencritic] WARNING: No OPENCRITIC_API_KEY env var set.")
            print("[opencritic] Using MOCK data mode for demonstration.")

        # ------------------------------------------------------------------
        # Mock mode
        # ------------------------------------------------------------------
        if not use_api:
            matched_games = find_matched_games(session)
            if not matched_games:
                print("[opencritic] No matching games found in DB.")
                print("[opencritic] Please run import_metacritic_kaggle.py first.")
                return

            print(f"[opencritic] Found {len(matched_games)} matched games in DB:")
            for g in matched_games:
                print(f"  - {g}")

            data = generate_mock_data(matched_games)

            # -- Sources --
            print(f"[opencritic] Inserting {len(data['sources'])} mock sources...")
            source_rows = []
            for src in data["sources"]:
                source_rows.append({
                    "source_id": oc_source_id_for(src["name"]),
                    "name": src["name"],
                    "source_type": "media",
                    "country_region": src["region"],
                    "language": src["language"],
                    "website_url": f"https://{src['name'].lower().replace(' ', '').replace('+', 'plus')}.com",
                    "is_institutional": 1,
                    "is_individual_creator": 0,
                    "inclusion_status": "active",
                    "notes": "OpenCritic mock source",
                    "created_at": now,
                    "updated_at": now,
                })
            _upsert_dicts(session, "sources", source_rows)
            print(f"[opencritic]   Inserted {len(source_rows)} sources.")

            # -- Reviews --
            print(f"[opencritic] Inserting {len(data['reviews'])} mock reviews...")

            # Clear previous mock reviews to avoid duplicates
            session.execute(text(
                "DELETE FROM reviews WHERE data_source = 'opencritic_mock'"
            ))
            session.commit()

            review_rows = []
            for rev in data["reviews"]:
                review_rows.append({
                    "review_id": rev["review_id"],
                    "target_id": None,  # no specific target for mock data
                    "game_id": rev["game_id"],
                    "source_id": rev["source_id"],
                    "reviewer_id": None,
                    "title": f"{rev['source_name']} review of {rev['game_title']}",
                    "original_score": str(int(rev["score"])),
                    "original_score_value": rev["score"],
                    "original_score_scale": 100.0,
                    "normalized_score": rev["score"],
                    "score_type": "numeric",
                    "review_url": rev["review_url"],
                    "review_date": rev["review_date"],
                    "platform": None,
                    "language": rev["language"],
                    "summary": f"Mock review from {rev['source_name']}. "
                               f"Score: {int(rev['score'])}/100.",
                    "positive_points": None,
                    "negative_points": None,
                    "has_review_code_disclosure": 0,
                    "has_sponsorship_disclosure": 0,
                    "data_source": "opencritic_mock",
                    "provenance_url": None,
                    "license_note": "Mock data for testing",
                    "created_at": now,
                    "updated_at": now,
                })

            _insert_dicts(session, "reviews", review_rows)
            print(f"[opencritic]   Inserted {len(review_rows)} reviews.")

            # -- Game identities --
            print(f"[opencritic] Inserting {len(data['identities'])} game identity entries...")
            _upsert_dicts(session, "game_identity", data["identities"])
            print(f"[opencritic]   Inserted {len(data['identities'])} identities.")

            session.commit()

        # ------------------------------------------------------------------
        # Final stats
        # ------------------------------------------------------------------
        print("\n[opencritic] === Import Summary ===")
        oc_sources = session.execute(
            text("SELECT COUNT(*) FROM sources WHERE notes LIKE '%OpenCritic%'")
        ).scalar()
        oc_reviews = session.execute(
            text("SELECT COUNT(*) FROM reviews WHERE data_source = 'opencritic_mock'")
        ).scalar()
        oc_identities = session.execute(
            text("SELECT COUNT(*) FROM game_identity WHERE source_name = 'opencritic_mock'")
        ).scalar()
        print(f"  OpenCritic sources:    {oc_sources}")
        print(f"  OpenCritic reviews:    {oc_reviews}")
        print(f"  OpenCritic identities: {oc_identities}")

        # Total DB stats
        for table in ["games", "sources", "reviews", "game_identity"]:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:25s} {count:>10,} total rows")

        print("[opencritic] Done.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        run_import()
    except Exception as exc:
        print(f"[opencritic] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
