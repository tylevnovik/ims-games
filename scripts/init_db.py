"""Initialize the IMS Games SQLite database with all required tables.

Usage:
    python init_db.py            # Create tables if they don't exist
    python init_db.py --rebuild  # Drop all tables and recreate
"""

import argparse
import sys

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DB_PATH, DB_URL, ensure_dirs

Base = declarative_base()


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------


class Game(Base):
    __tablename__ = "games"

    game_id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    title_original = Column(Text)
    release_date = Column(Text)
    release_year = Column(Integer)
    developer = Column(Text)
    publisher = Column(Text)
    genres = Column(Text)
    platforms = Column(Text)
    description = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class GameIdentity(Base):
    __tablename__ = "game_identity"

    identity_id = Column(String, primary_key=True)
    game_id = Column(String, nullable=False)  # FK -> games
    source_name = Column(Text, nullable=False)
    external_id = Column(Text)
    external_slug = Column(Text)
    external_title = Column(Text)
    external_url = Column(Text)
    match_confidence = Column(Float)
    match_method = Column(Text)
    needs_manual_review = Column(Integer, default=0)
    created_at = Column(Text)
    updated_at = Column(Text)


class ReviewTarget(Base):
    __tablename__ = "review_targets"

    target_id = Column(String, primary_key=True)
    game_id = Column(String, nullable=False)  # FK -> games
    platform = Column(Text)
    version_label = Column(Text)
    release_stage = Column(Text)
    region = Column(Text)
    language_scope = Column(Text)
    is_dlc = Column(Integer, default=0)
    is_remaster = Column(Integer, default=0)
    created_at = Column(Text)
    updated_at = Column(Text)


class Source(Base):
    __tablename__ = "sources"

    source_id = Column(String, primary_key=True)
    name = Column(Text, nullable=False)
    source_type = Column(Text)
    country_region = Column(Text)
    language = Column(Text)
    website_url = Column(Text)
    is_institutional = Column(Integer, default=1)
    is_individual_creator = Column(Integer, default=0)
    inclusion_status = Column(Text, default="active")
    notes = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class Reviewer(Base):
    __tablename__ = "reviewers"

    reviewer_id = Column(String, primary_key=True)
    source_id = Column(String, nullable=False)  # FK -> sources
    name = Column(Text)
    profile_url = Column(Text)
    expertise_tags = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class Review(Base):
    __tablename__ = "reviews"

    review_id = Column(String, primary_key=True)
    target_id = Column(String)  # FK -> review_targets (nullable: not all reviews have a target)
    game_id = Column(String, nullable=False)  # FK -> games
    source_id = Column(String, nullable=False)  # FK -> sources
    reviewer_id = Column(String)  # FK -> reviewers
    title = Column(Text)
    original_score = Column(Text)
    original_score_value = Column(Float)
    original_score_scale = Column(Float)
    normalized_score = Column(Float)
    score_type = Column(Text)
    review_url = Column(Text)
    review_date = Column(Text)
    platform = Column(Text)
    language = Column(Text)
    summary = Column(Text)
    positive_points = Column(Text)
    negative_points = Column(Text)
    has_review_code_disclosure = Column(Integer)
    has_sponsorship_disclosure = Column(Integer)
    data_source = Column(Text)
    provenance_url = Column(Text)
    license_note = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class ExternalBaseline(Base):
    __tablename__ = "external_baseline"

    baseline_id = Column(String, primary_key=True)
    game_id = Column(String, nullable=False)  # FK -> games
    target_id = Column(String)  # FK -> review_targets
    source_platform = Column(Text, nullable=False)
    external_score = Column(Float)
    external_user_score = Column(Float)
    review_count = Column(Integer)
    user_review_count = Column(Integer)
    source_url = Column(Text)
    collected_at = Column(Text)
    data_source = Column(Text)
    license_note = Column(Text)


class SourceMetric(Base):
    __tablename__ = "source_metrics"

    metric_id = Column(String, primary_key=True)
    source_id = Column(String, nullable=False)  # FK -> sources
    algorithm_version = Column(Text, nullable=False)
    sample_count = Column(Integer)
    mean_score = Column(Float)
    score_std = Column(Float)
    score_bias = Column(Float)
    discrimination_power = Column(Float)
    genre_coverage = Column(Text)
    platform_coverage = Column(Text)
    text_quality_score = Column(Float)
    disclosure_score = Column(Float)
    reliability_score = Column(Float)
    computed_at = Column(Text)


class Weight(Base):
    __tablename__ = "weights"

    weight_id = Column(String, primary_key=True)
    source_id = Column(String, nullable=False)  # FK -> sources
    algorithm_version = Column(Text, nullable=False)
    genre = Column(Text)
    platform = Column(Text)
    language = Column(Text)
    base_weight = Column(Float)
    context_weight = Column(Float)
    confidence = Column(Float)
    explanation = Column(Text)
    computed_at = Column(Text)


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    snapshot_id = Column(String, primary_key=True)
    game_id = Column(String, nullable=False)  # FK -> games
    target_id = Column(String)  # FK -> review_targets
    algorithm_version = Column(Text, nullable=False)
    raw_average = Column(Float)
    median_score = Column(Float)
    trimmed_mean = Column(Float)
    calibrated_score = Column(Float)
    weighted_score = Column(Float)
    sample_count = Column(Integer)
    source_count = Column(Integer)
    language_distribution = Column(Text)
    platform_distribution = Column(Text)
    score_std = Column(Float)
    computed_at = Column(Text)


# ---------------------------------------------------------------------------
# Database initialisation helpers
# ---------------------------------------------------------------------------

ALL_TABLES = [
    Game,
    GameIdentity,
    ReviewTarget,
    Source,
    Reviewer,
    Review,
    ExternalBaseline,
    SourceMetric,
    Weight,
    ScoreSnapshot,
]


INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_reviews_game_id ON reviews(game_id)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_source_id ON reviews(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_data_source ON reviews(data_source)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_game_data_source ON reviews(game_id, data_source)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_game_score ON reviews(game_id, normalized_score)",
    "CREATE INDEX IF NOT EXISTS idx_score_snapshots_game_version ON score_snapshots(game_id, algorithm_version)",
    "CREATE INDEX IF NOT EXISTS idx_score_snapshots_version_sample ON score_snapshots(algorithm_version, sample_count)",
    "CREATE INDEX IF NOT EXISTS idx_source_metrics_source_version ON source_metrics(source_id, algorithm_version)",
    "CREATE INDEX IF NOT EXISTS idx_weights_source_version ON weights(source_id, algorithm_version)",
    "CREATE INDEX IF NOT EXISTS idx_game_identity_source_external ON game_identity(source_name, external_id)",
    "CREATE INDEX IF NOT EXISTS idx_game_identity_game_id ON game_identity(game_id)",
    "CREATE INDEX IF NOT EXISTS idx_external_baseline_game_id ON external_baseline(game_id)",
    "CREATE INDEX IF NOT EXISTS idx_external_baseline_data_source ON external_baseline(data_source)",
]


def ensure_indexes(engine) -> None:
    """Create idempotent indexes used by import, scoring, and static export."""
    with engine.begin() as conn:
        for statement in INDEX_STATEMENTS:
            conn.execute(text(statement))
        conn.execute(text("PRAGMA optimize"))


def init_database(rebuild: bool = False) -> None:
    """Create (and optionally drop) all tables in the SQLite database."""
    ensure_dirs()

    # Ensure the parent directory for the DB file exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(DB_URL, echo=False)
    inspector = inspect(engine)

    if rebuild:
        print("[init_db] --rebuild flag set: dropping all existing tables...")
        Base.metadata.drop_all(engine)
        print("[init_db] All tables dropped.")

    existing = set(inspector.get_table_names())
    to_create = [t for t in ALL_TABLES if t.__tablename__ not in existing]

    if not to_create and not rebuild:
        ensure_indexes(engine)
        print("[init_db] All tables already exist. Indexes verified.")
        return

    # Create tables
    Base.metadata.create_all(engine)
    ensure_indexes(engine)

    created_names = [t.__tablename__ for t in ALL_TABLES]
    print(f"[init_db] Database ready at: {DB_PATH}")
    print(f"[init_db] Indexes verified ({len(INDEX_STATEMENTS)}).")
    print(f"[init_db] Tables ({len(created_names)}):")
    for name in created_names:
        status = "created" if name in [t.__tablename__ for t in to_create] or rebuild else "exists"
        print(f"  - {name:25s} [{status}]")

    # Quick verification
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        for model in ALL_TABLES:
            count = session.query(model).count()
            print(f"  {model.__tablename__:25s} rows: {count}")
    finally:
        session.close()

    print("[init_db] Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize IMS Games database.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop all tables and recreate from scratch.",
    )
    args = parser.parse_args()

    try:
        init_database(rebuild=args.rebuild)
    except Exception as exc:
        print(f"[init_db] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
