"""Generate media weights based on source_metrics.

For every source_metric record, calculates composite weight broken down
by source + genre + platform with human-readable English explanations.
"""

import json
import math
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from config import ALGORITHM_VERSION, DB_URL, ensure_dirs

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _clip(value, lo, hi):
    return max(lo, min(hi, value))


def _sample_confidence(sample_count):
    # Log scale keeps mature outlets distinct without letting giant archives dominate.
    raw = 0.6 + 0.5 * min(1.0, math.log1p(max(0, sample_count)) / math.log1p(5000))
    return _clip(raw, 0.6, 1.1)


def _discrimination_factor(disc_power):
    if disc_power is None:
        return 0.9
    return _clip(0.7 + 0.3 * disc_power, 0.7, 1.1)


def _genre_relevance(genre_name, genre_cov, total):
    if not genre_name or total == 0:
        return 1.0
    count = genre_cov.get(genre_name, 0)
    return _clip(0.8 + 0.4 * (count / total), 0.8, 1.2)


def _platform_relevance(plat_name, plat_cov, total):
    if not plat_name or total == 0:
        return 1.0
    count = plat_cov.get(plat_name, 0)
    return _clip(0.8 + 0.3 * (count / total), 0.8, 1.1)


def _build_explanation(source_name, genre, platform, sample_count, disc_factor, weight_val):
    parts = [f"{source_name}"]
    if genre:
        parts.append(f" ({genre})")
    if platform:
        parts.append(f" on {platform}")
    parts.append(f": {sample_count} historical reviews, ")
    if disc_factor >= 1.0:
        parts.append("high score discrimination")
    elif disc_factor >= 0.85:
        parts.append("moderate score discrimination")
    else:
        parts.append("low score discrimination")
    if sample_count >= 500:
        parts.append(", large historical sample")
    elif sample_count >= 100:
        parts.append(", sufficient sample size")
    elif sample_count >= 30:
        parts.append(", moderate sample size")
    else:
        parts.append(", limited sample size")
    parts.append(f" — final weight: {weight_val:.2f}")
    return "".join(parts)


def run() -> None:
    ensure_dirs()
    engine = create_engine(DB_URL, echo=False)

    with engine.begin() as conn:
        # Load metrics
        metrics = conn.execute(text("""
            SELECT sm.source_id, s.name, sm.sample_count,
                   sm.discrimination_power, sm.genre_coverage, sm.platform_coverage
            FROM source_metrics sm
            JOIN sources s ON s.source_id = sm.source_id
            WHERE sm.algorithm_version = :v
        """), {"v": ALGORITHM_VERSION}).fetchall()

        if not metrics:
            print(f"[WARN] No source_metric records for version {ALGORITHM_VERSION}.")
            print("       Run compute_source_metrics.py first.")
            return

        print(f"[INFO] Processing {len(metrics)} source metrics...")

        # Clear previous weights
        conn.execute(text(
            "DELETE FROM weights WHERE algorithm_version = :v"
        ), {"v": ALGORITHM_VERSION})

        written = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        for m in metrics:
            src_id = m[0]
            src_name = m[1]
            sample_count = m[2] or 0
            disc_power = m[3]
            genre_cov_raw = m[4]
            plat_cov_raw = m[5]

            try:
                genre_cov = json.loads(genre_cov_raw) if genre_cov_raw else {}
            except (json.JSONDecodeError, TypeError):
                genre_cov = {}
            try:
                plat_cov = json.loads(plat_cov_raw) if plat_cov_raw else {}
            except (json.JSONDecodeError, TypeError):
                plat_cov = {}

            base_weight = 1.0
            s_conf = _sample_confidence(sample_count)
            d_factor = _discrimination_factor(disc_power)
            disclosure = 0.95  # default for v0.1

            genres = list(genre_cov.keys()) if genre_cov else [None]
            platforms = list(plat_cov.keys()) if plat_cov else [None]

            for genre in genres:
                for platform in platforms:
                    g_rel = _genre_relevance(genre, genre_cov, sample_count)
                    p_rel = _platform_relevance(platform, plat_cov, sample_count)

                    ctx_weight = base_weight * s_conf * d_factor * g_rel * p_rel * disclosure

                    explanation = _build_explanation(
                        src_name, genre, platform, sample_count, d_factor, ctx_weight
                    )

                    weight_id = f"w-{src_id}-{genre or 'all'}-{platform or 'all'}-{ALGORITHM_VERSION}"

                    conn.execute(text("""
                        INSERT OR REPLACE INTO weights
                        (weight_id, source_id, algorithm_version, genre, platform,
                         language, base_weight, context_weight, confidence,
                         explanation, computed_at)
                        VALUES (:wid, :sid, :av, :genre, :plat,
                                NULL, :bw, :cw, :conf, :expl, :now)
                    """), {
                        "wid": weight_id, "sid": src_id, "av": ALGORITHM_VERSION,
                        "genre": genre, "plat": platform,
                        "bw": base_weight, "cw": round(ctx_weight, 6),
                        "conf": round(s_conf, 4), "expl": explanation, "now": now,
                    })
                    written += 1

            if written <= 20 or written % 100 == 0:
                print(f"  [OK] {src_name}: {len(genres)} genres x {len(platforms)} platforms, "
                      f"s_conf={s_conf:.2f}, disc={d_factor:.2f}")

        print(f"\n[DONE] Wrote {written} weight records.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"[compute_weights] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
