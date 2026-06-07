"""Import Metacritic review data from the Kaggle CSV into the IMS Games database.

Reads:
    - data/metacritic/reviews.csv  (required: ID, Game, Website, Review, Score)
    - data/metacritic/reviews_with_release_dates.parquet  (optional: adds release dates)

Usage:
    python import_metacritic_kaggle.py
"""

import hashlib
import sys
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import (
    ALGORITHM_VERSION,
    DB_URL,
    METACRITIC_CSV,
    METACRITIC_PARQUET,
    ensure_dirs,
)
from source_identity import canonical_source_name, source_id_for_name


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# ---------------------------------------------------------------------------


def _md5(text: str) -> str:
    """Return the hex MD5 digest of a UTF-8 encoded string."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def game_id_for(title: str) -> str:
    return f"mc-{_md5(title)[:16]}"


def source_id_for(website: str) -> str:
    return source_id_for_name(website)


def review_id_for(row_id: int) -> str:
    return f"mc-rev-{row_id}"


def target_id_for(title: str) -> str:
    return f"mc-tgt-{_md5(title)[:16]}"


def baseline_id_for(title: str) -> str:
    return f"mc-bl-{_md5(title)[:16]}"


def identity_id_for(title: str) -> str:
    return f"mc-id-{_md5(title)[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_csv() -> pd.DataFrame:
    """Load the main Metacritic reviews CSV."""
    print(f"[import] Reading CSV: {METACRITIC_CSV}")
    df = pd.read_csv(METACRITIC_CSV, encoding="utf-8")
    # Normalise column names (strip whitespace / control chars)
    df.columns = [c.strip() for c in df.columns]
    print(f"[import] CSV loaded: {len(df):,} rows, columns={list(df.columns)}")
    return df


def load_parquet_dates() -> dict:
    """Try to load the parquet file and return a {game_title: release_date} map."""
    if not METACRITIC_PARQUET.exists():
        print(f"[import] Parquet not found at {METACRITIC_PARQUET}, skipping release dates.")
        return {}

    try:
        print(f"[import] Reading parquet for release dates: {METACRITIC_PARQUET}")
        pq = pd.read_parquet(METACRITIC_PARQUET)
        # Normalise column names (the parquet has 'Score\r' etc.)
        pq.columns = [c.strip().replace("\r", "") for c in pq.columns]
        print(f"[import] Parquet loaded: {len(pq):,} rows, columns={list(pq.columns)}")

        if "release_date" in pq.columns:
            date_map = (
                pq.dropna(subset=["release_date"])
                .groupby("Game")["release_date"]
                .first()
                .to_dict()
            )
            print(f"[import] Release dates available for {len(date_map):,} games.")
            return date_map
        else:
            print("[import] Parquet has no 'release_date' column.")
            return {}
    except Exception as exc:
        print(f"[import] WARNING: Could not read parquet: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------


def run_import() -> None:
    ensure_dirs()
    now = _now()

    # -- Load data --
    df = load_csv()
    date_map = load_parquet_dates()

    # Coerce Score to numeric (handles any stray whitespace / text)
    df["Score"] = pd.to_numeric(df["Score"].astype(str).str.strip(), errors="coerce")
    df = df.dropna(subset=["Score"])
    df["Score"] = df["Score"].astype(float)

    # -- Connect to DB --
    engine = create_engine(DB_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # ------------------------------------------------------------------
        # 1. Build unique games
        # ------------------------------------------------------------------
        print("[import] Building game entries...")
        unique_games = df["Game"].unique()
        print(f"[import]   {len(unique_games):,} unique games found.")

        game_rows = []
        for title in unique_games:
            gid = game_id_for(title)
            release_date = date_map.get(title)
            release_year = None
            if release_date:
                try:
                    release_year = int(str(release_date)[:4])
                except (ValueError, TypeError):
                    pass

            game_rows.append({
                "game_id": gid,
                "title": title,
                "title_original": None,
                "release_date": str(release_date) if release_date else None,
                "release_year": release_year,
                "developer": None,
                "publisher": None,
                "genres": None,
                "platforms": None,
                "description": None,
                "created_at": now,
                "updated_at": now,
            })

        # Upsert games (INSERT OR REPLACE handles idempotency)
        _upsert_dicts(session, "games", game_rows)
        print(f"[import]   Inserted {len(game_rows):,} games.")

        # ------------------------------------------------------------------
        # 2. Build unique sources (websites)
        # ------------------------------------------------------------------
        print("[import] Building source entries...")
        unique_websites = df["Website"].unique()
        print(f"[import]   {len(unique_websites):,} unique sources found.")

        source_rows = []
        for website in unique_websites:
            canonical_name = canonical_source_name(website)
            source_rows.append({
                "source_id": source_id_for(canonical_name),
                "name": canonical_name,
                "source_type": "media",
                "country_region": None,
                "language": "en",
                "website_url": None,
                "is_institutional": 1,
                "is_individual_creator": 0,
                "inclusion_status": "active",
                "notes": "Imported from Metacritic Kaggle dataset",
                "created_at": now,
                "updated_at": now,
            })

        _upsert_dicts(session, "sources", source_rows)
        print(f"[import]   Inserted {len(source_rows):,} sources.")

        # ------------------------------------------------------------------
        # 3. Build review targets (one per game, generic)
        # ------------------------------------------------------------------
        print("[import] Building review target entries...")
        target_rows = []
        for title in unique_games:
            target_rows.append({
                "target_id": target_id_for(title),
                "game_id": game_id_for(title),
                "platform": None,
                "version_label": None,
                "release_stage": "release",
                "region": None,
                "language_scope": None,
                "is_dlc": 0,
                "is_remaster": 0,
                "created_at": now,
                "updated_at": now,
            })

        _upsert_dicts(session, "review_targets", target_rows)
        print(f"[import]   Inserted {len(target_rows):,} review targets.")

        # ------------------------------------------------------------------
        # 4. Build reviews (one per CSV row)
        # ------------------------------------------------------------------
        print("[import] Building review entries (this may take a moment)...")

        # Pre-build lookup maps for speed
        game_id_map = {title: game_id_for(title) for title in unique_games}
        source_id_map = {ws: source_id_for(ws) for ws in unique_websites}
        target_id_map = {title: target_id_for(title) for title in unique_games}

        # Process in chunks for progress reporting
        chunk_size = 50_000
        total_inserted = 0

        # Clear existing Metacritic reviews first
        session.execute(text("DELETE FROM reviews WHERE data_source = 'metacritic_kaggle'"))
        session.commit()

        for start in range(0, len(df), chunk_size):
            chunk = df.iloc[start : start + chunk_size]
            review_rows = []
            for _, row in chunk.iterrows():
                rid = review_id_for(int(row["ID"]))
                gid = game_id_map[row["Game"]]
                sid = source_id_map[row["Website"]]
                tid = target_id_map[row["Game"]]
                score = float(row["Score"])

                review_rows.append({
                    "review_id": rid,
                    "target_id": tid,
                    "game_id": gid,
                    "source_id": sid,
                    "reviewer_id": None,
                    "title": None,
                    "original_score": str(score),
                    "original_score_value": score,
                    "original_score_scale": 100.0,
                    "normalized_score": score,  # already on 0-100 scale
                    "score_type": "numeric",
                    "review_url": None,
                    "review_date": None,
                    "platform": None,
                    "language": "en",
                    "summary": _truncate(str(row.get("Review", "")), 2000),
                    "positive_points": None,
                    "negative_points": None,
                    "has_review_code_disclosure": None,
                    "has_sponsorship_disclosure": None,
                    "data_source": "metacritic_kaggle",
                    "provenance_url": None,
                    "license_note": "Metacritic Kaggle dataset",
                    "created_at": now,
                    "updated_at": now,
                })

            _insert_dicts(session, "reviews", review_rows)
            total_inserted += len(review_rows)
            print(f"[import]   Reviews inserted: {total_inserted:,} / {len(df):,}")

        print(f"[import]   Total reviews: {total_inserted:,}")

        # ------------------------------------------------------------------
        # 5. Build external_baseline (aggregate Metacritic score per game)
        # ------------------------------------------------------------------
        print("[import] Building external baseline entries...")
        agg = (
            df.groupby("Game")
            .agg(
                mean_score=("Score", "mean"),
                review_count=("Score", "count"),
            )
            .reset_index()
        )

        baseline_rows = []
        for _, row in agg.iterrows():
            title = row["Game"]
            baseline_rows.append({
                "baseline_id": baseline_id_for(title),
                "game_id": game_id_for(title),
                "target_id": target_id_for(title),
                "source_platform": "metacritic",
                "external_score": round(float(row["mean_score"]), 2),
                "external_user_score": None,
                "review_count": int(row["review_count"]),
                "user_review_count": None,
                "source_url": None,
                "collected_at": now,
                "data_source": "metacritic_kaggle",
                "license_note": "Metacritic Kaggle dataset",
            })

        _upsert_dicts(session, "external_baseline", baseline_rows)
        print(f"[import]   Inserted {len(baseline_rows):,} baseline entries.")

        # ------------------------------------------------------------------
        # 6. Build game_identity entries
        # ------------------------------------------------------------------
        print("[import] Building game identity entries...")
        identity_rows = []
        for title in unique_games:
            slug = title.lower().replace(" ", "-").replace(":", "")
            identity_rows.append({
                "identity_id": identity_id_for(title),
                "game_id": game_id_for(title),
                "source_name": "metacritic_kaggle",
                "external_id": None,
                "external_slug": slug,
                "external_title": title,
                "external_url": None,
                "match_confidence": 1.0,
                "match_method": "exact_title",
                "needs_manual_review": 0,
                "created_at": now,
                "updated_at": now,
            })

        _upsert_dicts(session, "game_identity", identity_rows)
        print(f"[import]   Inserted {len(identity_rows):,} identity entries.")

        session.commit()

        # ------------------------------------------------------------------
        # Final stats
        # ------------------------------------------------------------------
        print("\n[import] === Import Summary ===")
        for table in ["games", "sources", "review_targets", "reviews",
                       "external_baseline", "game_identity"]:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:25s} {count:>10,} rows")
        print("[import] Done.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Bulk insert helpers
# ---------------------------------------------------------------------------


def _upsert_dicts(session, table_name: str, rows: list[dict]) -> None:
    """Insert rows using INSERT OR REPLACE for idempotency."""
    if not rows:
        return
    columns = list(rows[0].keys())
    cols_sql = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = f"INSERT OR REPLACE INTO {table_name} ({cols_sql}) VALUES ({placeholders})"
    session.execute(text(sql), rows)
    session.commit()


def _insert_dicts(session, table_name: str, rows: list[dict]) -> None:
    """Plain INSERT (used when table was already cleared)."""
    if not rows:
        return
    columns = list(rows[0].keys())
    cols_sql = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders})"
    session.execute(text(sql), rows)
    session.commit()


def _truncate(s: str, max_len: int) -> str | None:
    if not s or s == "nan":
        return None
    return s[:max_len] if len(s) > max_len else s


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        run_import()
    except Exception as exc:
        print(f"[import] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
