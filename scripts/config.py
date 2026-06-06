"""Shared configuration for IMS Games data pipeline."""

import os
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_DIR = DATA_DIR / "db"
LOG_DIR = DATA_DIR / "logs"
SITE_DATA_DIR = PROJECT_ROOT / "site" / "public" / "data"

# Database
DB_PATH = DB_DIR / "ims_games.sqlite"
DB_URL = f"sqlite:///{DB_PATH}"

# Algorithm version
ALGORITHM_VERSION = "0.1.0"

# Data source paths
METACRITIC_CSV = DATA_DIR / "metacritic" / "reviews.csv"
METACRITIC_PARQUET = DATA_DIR / "metacritic" / "reviews_with_release_dates.parquet"
OPENCRITIC_DIR = DATA_DIR / "opencritic"

# Environment variables
OPENCRITIC_API_KEY = os.environ.get("OPENCRITIC_API_KEY", "")

# Score normalization constants
SCORE_SCALE = 100.0
MIN_SAMPLE_FOR_CALIBRATION = 10
MIN_SAMPLE_FOR_TRIMMING = 20
TRIM_PERCENTAGE = 0.05

# Weight boundaries
WEIGHT_RANGES = {
    "sample_confidence": (0.6, 1.1),
    "discrimination_factor": (0.7, 1.1),
    "genre_relevance": (0.8, 1.2),
    "platform_relevance": (0.8, 1.1),
    "disclosure_factor": (0.9, 1.05),
}

# Letter grade mapping
LETTER_GRADE_MAP = {
    "A+": 97, "A": 90, "A-": 87,
    "B+": 83, "B": 80, "B-": 77,
    "C+": 73, "C": 70, "C-": 67,
    "D+": 63, "D": 60, "D-": 57,
    "F": 40,
}


def ensure_dirs():
    """Create necessary directories if they don't exist."""
    for d in [DB_DIR, LOG_DIR, SITE_DATA_DIR]:
        d.mkdir(parents=True, exist_ok=True)
