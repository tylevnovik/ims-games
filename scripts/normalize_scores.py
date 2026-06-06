"""Score normalization script.

Converts all review scores to a uniform 0-100 scale.
"""

import re
import sys
from collections import defaultdict

from sqlalchemy import create_engine, text

from config import DB_URL, LETTER_GRADE_MAP, ensure_dirs

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
_LETTER_RE = re.compile(r"^\s*([ABCDF][+-]?)\s*$", re.IGNORECASE)
_FRACTION_RE = re.compile(r"^\s*([\d.]+)\s*/\s*([\d.]+)\s*$")


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _try_float(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def normalize_score(original_score_value, original_score_scale, score_type) -> tuple[float | None, str, str]:
    """Returns (normalized_value, score_type, rule_applied)."""
    if original_score_value is None:
        return (None, "non_numeric", "empty_value")

    raw_str = str(original_score_value).strip()
    if not raw_str:
        return (None, "non_numeric", "empty_value")

    # Letter grade
    letter_match = _LETTER_RE.match(raw_str)
    if letter_match:
        grade = letter_match.group(1).upper()
        if grade in LETTER_GRADE_MAP:
            return (_clamp(float(LETTER_GRADE_MAP[grade])), "numeric", f"letter:{grade}")
        return (None, "non_numeric", f"unknown_letter:{grade}")

    # Fractional
    frac_match = _FRACTION_RE.match(raw_str)
    if frac_match:
        num = _try_float(frac_match.group(1))
        den = _try_float(frac_match.group(2))
        if num is not None and den and den > 0:
            return (_clamp((num / den) * 100.0), "numeric", f"fraction:{num}/{den}")
        return (None, "non_numeric", "unparseable_fraction")

    # Plain number
    numeric = _try_float(raw_str)
    if numeric is None:
        return (None, "non_numeric", "unparseable_value")

    scale = _try_float(original_score_scale)
    if scale is not None:
        if scale == 100:
            return (_clamp(numeric), "numeric", "scale_100")
        if scale == 10:
            return (_clamp(numeric * 10), "numeric", "scale_10")
        if scale == 5:
            return (_clamp(numeric * 20), "numeric", "scale_5")
        if scale == 4:
            return (_clamp(numeric * 25), "numeric", "scale_4_star")
        if scale > 0:
            return (_clamp((numeric / scale) * 100.0), "numeric", f"scale_custom:{scale}")

    if score_type == "non_numeric":
        return (None, "non_numeric", "pre_marked_non_numeric")

    return (None, "non_numeric", "no_scale_info")


def run() -> None:
    ensure_dirs()
    engine = create_engine(DB_URL, echo=False)

    # Load all reviews
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT review_id, original_score, original_score_value,
                   original_score_scale, normalized_score, score_type
            FROM reviews
        """)).fetchall()

    if not rows:
        print("[normalize_scores] No reviews found.")
        return

    print(f"[normalize_scores] Processing {len(rows):,} reviews...")

    rule_counts: dict[str, int] = defaultdict(int)
    scale_dist: dict[str, int] = defaultdict(int)
    converted = 0
    non_numeric = 0
    updates: list[dict] = []

    for row in rows:
        r = dict(row._mapping)
        norm_val, stype, rule = normalize_score(
            r["original_score_value"], r["original_score_scale"], r["score_type"]
        )
        rule_counts[rule] += 1
        scale_dist[str(r["original_score_scale"])] += 1

        if norm_val is not None:
            converted += 1
        else:
            non_numeric += 1

        updates.append({
            "review_id": r["review_id"],
            "normalized_score": norm_val,
            "score_type": stype,
        })

    # Batch update
    with engine.begin() as conn:
        batch_size = 10000
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            for upd in batch:
                conn.execute(text("""
                    UPDATE reviews
                    SET normalized_score = :ns, score_type = :st
                    WHERE review_id = :rid
                """), {"ns": upd["normalized_score"], "st": upd["score_type"], "rid": upd["review_id"]})

    print(f"\n=== Score Normalization Summary ===")
    print(f"  Total reviews processed : {len(rows):,}")
    print(f"  Converted to 0-100      : {converted:,}")
    print(f"  Non-numeric (null)      : {non_numeric:,}")
    print(f"\n  Distribution of original_score_scale:")
    for label in sorted(scale_dist.keys(), key=lambda x: (x == "None", x)):
        print(f"    {label:>12s} : {scale_dist[label]:,}")
    print(f"\n  Conversion rules applied:")
    for rule in sorted(rule_counts.keys()):
        print(f"    {rule:35s} : {rule_counts[rule]:,}")
    print(f"===================================\n")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"[normalize_scores] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
