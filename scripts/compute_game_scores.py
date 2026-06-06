"""Compute aggregate scores for each game.

OPTIMIZED: bulk loads all data, computes in memory, batch inserts.
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy.stats import trim_mean as scipy_trim_mean
from sqlalchemy import create_engine, text

from config import (
    ALGORITHM_VERSION, DB_URL, MIN_SAMPLE_FOR_CALIBRATION,
    MIN_SAMPLE_FOR_TRIMMING, ensure_dirs,
)


def _clamp(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, value))


def _parse_list(raw):
    if not raw:
        return []
    try:
        result = json.loads(raw) if raw.startswith("[") else [x.strip() for x in raw.split("|")]
        return [str(x).strip() for x in result if x]
    except (json.JSONDecodeError, TypeError):
        return [x.strip() for x in str(raw).split("|") if x.strip()]


def _find_weight(source_id, genres, platforms, w_lookup):
    """Find best matching weight with progressive fallback."""
    for g in (genres or [None]):
        for p in (platforms or [None]):
            key = (source_id, g, p)
            if key in w_lookup:
                return w_lookup[key]
    for g in (genres or [None]):
        key = (source_id, g, None)
        if key in w_lookup:
            return w_lookup[key]
    for p in (platforms or [None]):
        key = (source_id, None, p)
        if key in w_lookup:
            return w_lookup[key]
    key = (source_id, None, None)
    return w_lookup.get(key, 1.0)


def run() -> None:
    ensure_dirs()
    engine = create_engine(DB_URL, echo=False)

    with engine.begin() as conn:
        # --- Bulk load everything in a few queries ---
        print("[INFO] Loading all reviews...")
        all_reviews = conn.execute(text("""
            SELECT game_id, source_id, normalized_score, language, platform
            FROM reviews WHERE normalized_score IS NOT NULL
        """)).fetchall()
        print(f"[INFO] Loaded {len(all_reviews):,} reviews")

        if not all_reviews:
            print("[WARN] No valid scores found.")
            return

        sm_rows = conn.execute(text("""
            SELECT source_id, sample_count, mean_score, score_std
            FROM source_metrics WHERE algorithm_version = :v
        """), {"v": ALGORITHM_VERSION}).fetchall()
        sm_lookup = {r[0]: (r[1], r[2], r[3]) for r in sm_rows}

        w_rows = conn.execute(text("""
            SELECT source_id, genre, platform, context_weight
            FROM weights WHERE algorithm_version = :v
        """), {"v": ALGORITHM_VERSION}).fetchall()
        w_lookup = {(r[0], r[1], r[2]): r[3] for r in w_rows}

        games_rows = conn.execute(text(
            "SELECT game_id, title, genres, platforms FROM games"
        )).fetchall()

        # Global stats
        global_arr = np.array([r[2] for r in all_reviews], dtype=np.float64)
        global_mean = float(np.mean(global_arr))
        global_std = float(np.std(global_arr, ddof=0))

        print(f"[INFO] Global mean: {global_mean:.2f}, std: {global_std:.2f}")
        print(f"[INFO] Source metrics: {len(sm_lookup)}, Weights: {len(w_lookup)}, Games: {len(games_rows)}")

        # --- Group reviews by game_id in memory ---
        reviews_by_game: dict[str, list] = defaultdict(list)
        for r in all_reviews:
            reviews_by_game[r[0]].append(r)

        # Clear previous
        conn.execute(text(
            "DELETE FROM score_snapshots WHERE algorithm_version = :v"
        ), {"v": ALGORITHM_VERSION})

        # --- Compute in memory ---
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        insert_rows: list[dict] = []
        skipped = 0

        for game in games_rows:
            gid = game[0]
            game_reviews = reviews_by_game.get(gid)
            if not game_reviews:
                skipped += 1
                continue

            game_genres = _parse_list(game[2])
            game_platforms = _parse_list(game[3])

            scores = np.array([r[2] for r in game_reviews], dtype=np.float64)
            sample_count = len(scores)
            source_count = len(set(r[1] for r in game_reviews))

            raw_average = float(np.mean(scores))
            median_score = float(np.median(scores))
            trimmed_mean = (
                float(scipy_trim_mean(scores, proportiontocut=0.05))
                if sample_count >= MIN_SAMPLE_FOR_TRIMMING else raw_average
            )

            # Calibrated
            cal_values = []
            for r in game_reviews:
                sm = sm_lookup.get(r[1])
                if sm and sm[0] and sm[0] >= MIN_SAMPLE_FOR_CALIBRATION:
                    src_mean = sm[1] or global_mean
                    src_std = sm[2] if sm[2] and sm[2] > 0 else 1.0
                    cal_values.append(_clamp(global_mean + ((r[2] - src_mean) / src_std) * global_std))
                else:
                    cal_values.append(_clamp(r[2]))
            calibrated_score = _clamp(float(np.mean(cal_values)))

            # Weighted
            w_sum = 0.0
            w_total = 0.0
            for r in game_reviews:
                w = _find_weight(r[1], game_genres, game_platforms, w_lookup)
                w_sum += r[2] * w
                w_total += w
            weighted_score = w_sum / w_total if w_total > 0 else raw_average

            # Distributions
            lang_c = Counter(r[3] for r in game_reviews if r[3])
            plat_c = Counter(r[4] for r in game_reviews if r[4])

            insert_rows.append({
                "sid": f"snap-{gid}-{ALGORITHM_VERSION}",
                "gid": gid, "av": ALGORITHM_VERSION,
                "ra": round(raw_average, 4), "ms": round(median_score, 4),
                "tm": round(trimmed_mean, 4), "cs": round(calibrated_score, 4),
                "ws": round(weighted_score, 4), "sc": sample_count,
                "src": source_count,
                "ld": json.dumps(dict(lang_c), ensure_ascii=False),
                "pd": json.dumps(dict(plat_c), ensure_ascii=False),
                "ss": round(float(np.std(scores, ddof=0)), 4), "now": now,
            })

        # --- Batch insert ---
        print(f"[INFO] Batch inserting {len(insert_rows)} snapshots...")
        if insert_rows:
            conn.execute(text("""
                INSERT OR REPLACE INTO score_snapshots
                (snapshot_id, game_id, target_id, algorithm_version,
                 raw_average, median_score, trimmed_mean, calibrated_score,
                 weighted_score, sample_count, source_count,
                 language_distribution, platform_distribution, score_std, computed_at)
                VALUES (:sid, :gid, NULL, :av, :ra, :ms, :tm, :cs,
                        :ws, :sc, :src, :ld, :pd, :ss, :now)
            """), insert_rows)

        print(f"\n[DONE] Wrote {len(insert_rows)} snapshots, skipped {skipped} games.")
        ws = [r["ws"] for r in insert_rows]
        if ws:
            print(f"  Total: {len(ws)}, Mean: {np.mean(ws):.2f}, "
                  f"Std: {np.std(ws):.2f}, Min: {min(ws):.2f}, Max: {max(ws):.2f}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"[compute_game_scores] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
