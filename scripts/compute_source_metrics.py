"""Compute historical performance metrics for each media source.

For every source, calculates mean, std, bias, discrimination power,
genre/platform coverage. Results written to source_metrics table.
"""

import json
import sys
from collections import defaultdict

import numpy as np
from sqlalchemy import create_engine, text

from config import ALGORITHM_VERSION, DB_URL, ensure_dirs

MIN_REVIEWS = 3


def run() -> None:
    ensure_dirs()
    engine = create_engine(DB_URL, echo=False)

    with engine.begin() as conn:
        # Global stats
        all_scores = conn.execute(text(
            "SELECT normalized_score FROM reviews WHERE normalized_score IS NOT NULL"
        )).fetchall()

        if not all_scores:
            print("[compute_source_metrics] No valid scores found.")
            return

        global_arr = np.array([r[0] for r in all_scores], dtype=np.float64)
        global_mean = float(np.mean(global_arr))
        global_std = float(np.std(global_arr, ddof=0))

        print(f"[INFO] Global mean: {global_mean:.2f}, std: {global_std:.2f}")
        print(f"[INFO] Algorithm version: {ALGORITHM_VERSION}\n")

        # Get all sources
        sources = conn.execute(text("SELECT source_id, name FROM sources")).fetchall()
        if not sources:
            print("[WARN] No sources found.")
            return

        # Clear previous metrics
        conn.execute(text(
            "DELETE FROM source_metrics WHERE algorithm_version = :v"
        ), {"v": ALGORITHM_VERSION})

        written = 0
        skipped = 0

        for src in sources:
            src_id = src[0]
            src_name = src[1]

            # Get reviews for this source with valid scores
            reviews = conn.execute(text("""
                SELECT r.normalized_score, g.genres, g.platforms
                FROM reviews r
                JOIN games g ON g.game_id = r.game_id
                WHERE r.source_id = :sid AND r.normalized_score IS NOT NULL
            """), {"sid": src_id}).fetchall()

            if len(reviews) < MIN_REVIEWS:
                skipped += 1
                continue

            scores = np.array([r[0] for r in reviews], dtype=np.float64)
            sample_count = len(scores)
            mean_score = float(np.mean(scores))
            score_std = float(np.std(scores, ddof=0))
            score_bias = mean_score - global_mean

            discrimination_power = (
                min(1.0, score_std / global_std) if global_std > 0 else 0.0
            )

            # Genre coverage
            genre_cov: dict[str, int] = defaultdict(int)
            plat_cov: dict[str, int] = defaultdict(int)
            for r in reviews:
                genres_raw = r[1]
                platforms_raw = r[2]
                if genres_raw:
                    try:
                        genres = json.loads(genres_raw) if genres_raw.startswith("[") else [g.strip() for g in genres_raw.split("|")]
                    except (json.JSONDecodeError, TypeError):
                        genres = [g.strip() for g in str(genres_raw).split("|") if g.strip()]
                    for g in genres:
                        if isinstance(g, str) and g.strip():
                            genre_cov[g.strip()] += 1
                if platforms_raw:
                    try:
                        plats = json.loads(platforms_raw) if platforms_raw.startswith("[") else [p.strip() for p in platforms_raw.split("|")]
                    except (json.JSONDecodeError, TypeError):
                        plats = [p.strip() for p in str(platforms_raw).split("|") if p.strip()]
                    for p in plats:
                        if isinstance(p, str) and p.strip():
                            plat_cov[p.strip()] += 1

            metric_id = f"sm-{src_id}-{ALGORITHM_VERSION}"
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            conn.execute(text("""
                INSERT OR REPLACE INTO source_metrics
                (metric_id, source_id, algorithm_version, sample_count,
                 mean_score, score_std, score_bias, discrimination_power,
                 genre_coverage, platform_coverage, text_quality_score,
                 disclosure_score, reliability_score, computed_at)
                VALUES (:mid, :sid, :av, :sc, :ms, :ss, :sb, :dp,
                        :gc, :pc, NULL, NULL, NULL, :now)
            """), {
                "mid": metric_id, "sid": src_id, "av": ALGORITHM_VERSION,
                "sc": sample_count, "ms": round(mean_score, 4),
                "ss": round(score_std, 4), "sb": round(score_bias, 4),
                "dp": round(discrimination_power, 4),
                "gc": json.dumps(dict(genre_cov), ensure_ascii=False),
                "pc": json.dumps(dict(plat_cov), ensure_ascii=False),
                "now": now,
            })
            written += 1

            if written <= 10 or written % 50 == 0:
                print(f"  [OK] {src_name}: n={sample_count}, mean={mean_score:.1f}, "
                      f"std={score_std:.1f}, bias={score_bias:+.1f}")

        print(f"\n[DONE] Wrote {written} source metrics, skipped {skipped} sources.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"[compute_source_metrics] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
