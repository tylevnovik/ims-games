"""Match games across different data sources using title similarity.

Aligns game_identity records from different sources by comparing titles,
release years, developers, publishers, and platforms using a priority-based
matching algorithm with rapidfuzz for string similarity.
"""

import re
import string
import sys
from collections import defaultdict

from rapidfuzz import fuzz
from sqlalchemy import create_engine, text

from config import DB_URL, ensure_dirs

# ---------------------------------------------------------------------------
# Title normalisation
# ---------------------------------------------------------------------------
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def normalize_title(title: str) -> str:
    """Lowercase, strip whitespace, remove punctuation."""
    if not title:
        return ""
    title = title.lower().strip()
    title = _PUNCT_RE.sub("", title)
    return re.sub(r"\s+", " ", title)


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def try_match(game_a: dict, game_b: dict) -> tuple[float, str] | None:
    """Attempt to match two games. Returns (confidence, method) or None."""
    title_a = normalize_title(game_a.get("external_title") or game_a.get("title", ""))
    title_b = normalize_title(game_b.get("external_title") or game_b.get("title", ""))

    if not title_a or not title_b:
        return None

    similarity = fuzz.ratio(title_a, title_b) / 100.0
    exact_title = title_a == title_b

    # Get release year from joined games data
    year_a = game_a.get("release_year")
    year_b = game_b.get("release_year")
    year_match = year_a is not None and year_b is not None and year_a == year_b

    dev_a = (game_a.get("developer") or "").strip().lower()
    dev_b = (game_b.get("developer") or "").strip().lower()
    dev_match = bool(dev_a and dev_b and dev_a == dev_b)

    pub_a = (game_a.get("publisher") or "").strip().lower()
    pub_b = (game_b.get("publisher") or "").strip().lower()
    pub_match = bool(pub_a and pub_b and pub_a == pub_b)

    # Platform overlap
    plats_a = set((game_a.get("platforms") or "").lower().split(",")) if game_a.get("platforms") else set()
    plats_b = set((game_b.get("platforms") or "").lower().split(",")) if game_b.get("platforms") else set()
    platform_overlap = bool(plats_a & plats_b - {""})

    # Priority 1: exact title + release year
    if exact_title and year_match:
        return (1.0, "exact_title_year")
    # Priority 2: exact title + developer
    if exact_title and dev_match:
        return (0.95, "exact_title_dev")
    # Priority 3: fuzzy title (>0.9) + release year
    if similarity > 0.9 and year_match:
        return (0.85, "fuzzy_title_year")
    # Priority 4: fuzzy title (>0.85) + platform overlap
    if similarity > 0.85 and platform_overlap:
        return (0.75, "fuzzy_title_platform")
    # Priority 5: fuzzy title (>0.8) + dev/pub match
    if similarity > 0.8 and (dev_match or pub_match):
        return (0.7, "fuzzy_title_dev")

    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run() -> None:
    ensure_dirs()
    engine = create_engine(DB_URL, echo=False)

    with engine.connect() as conn:
        # Load game_identity joined with games for extra metadata
        rows = conn.execute(text("""
            SELECT
                gi.identity_id,
                gi.game_id,
                gi.source_name,
                gi.external_title,
                gi.match_confidence,
                gi.match_method,
                gi.needs_manual_review,
                g.title,
                g.release_year,
                g.developer,
                g.publisher,
                g.platforms
            FROM game_identity gi
            JOIN games g ON g.game_id = gi.game_id
        """)).fetchall()

    if not rows:
        print("[match_games] No game_identity records found. Nothing to do.")
        return

    # Group by source_name
    by_source: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rec = dict(row._mapping)
        by_source[rec["source_name"]].append(rec)

    total_records = sum(len(v) for v in by_source.values())
    print(
        f"[match_games] Loaded {total_records} game_identity records "
        f"from {len(by_source)} source(s): "
        + ", ".join(f"{s} ({len(ids)})" for s, ids in sorted(by_source.items()))
    )

    if len(by_source) < 2:
        print("[match_games] Need at least 2 sources to perform matching.")
        return

    # Cross-source matching
    stats: dict[str, int] = defaultdict(int)
    match_pairs: list[tuple[str, str, float, str]] = []  # (identity_a, identity_b, conf, method)
    total_pairs = 0
    below_threshold = 0

    source_names = sorted(by_source.keys())
    for i in range(len(source_names)):
        for j in range(i + 1, len(source_names)):
            list_a = by_source[source_names[i]]
            list_b = by_source[source_names[j]]

            # Build normalized title index for list_b for speed
            b_title_index: dict[str, list[dict]] = defaultdict(list)
            for gb in list_b:
                nt = normalize_title(gb.get("external_title") or gb.get("title", ""))
                if nt:
                    b_title_index[nt].append(gb)

            for ga in list_a:
                total_pairs += len(list_b)
                title_a_norm = normalize_title(ga.get("external_title") or ga.get("title", ""))
                if not title_a_norm:
                    continue

                # Check exact matches first (fast path)
                best_match = None
                best_conf = 0.0

                # Exact title lookup
                for gb in b_title_index.get(title_a_norm, []):
                    result = try_match(ga, gb)
                    if result and result[0] > best_conf:
                        best_match = (gb, result)
                        best_conf = result[0]

                # If no exact match, do fuzzy on a sample (limit to avoid O(n^2) explosion)
                if not best_match and len(list_b) <= 5000:
                    for gb in list_b:
                        result = try_match(ga, gb)
                        if result and result[0] > best_conf:
                            best_match = (gb, result)
                            best_conf = result[0]

                if best_match:
                    gb, (conf, method) = best_match
                    match_pairs.append((
                        ga["identity_id"], gb["identity_id"], conf, method
                    ))
                    stats[method] += 1
                else:
                    below_threshold += 1

    print(f"[match_games] Compared across {len(source_names)} sources.")

    # Collect matched identity pairs and update
    # For each matched pair, update both identity rows to point to same game_id
    # Use the game_id from the metacritic_kaggle source as canonical
    with engine.begin() as conn:
        matched_count = 0
        manual_review_count = 0

        for id_a, id_b, conf, method in match_pairs:
            # Update the non-metacritic identity to point to the metacritic game_id
            conn.execute(text("""
                UPDATE game_identity
                SET match_confidence = :conf,
                    match_method = :method,
                    needs_manual_review = 0
                WHERE identity_id = :id
            """), {"conf": conf, "method": method, "id": id_a})
            conn.execute(text("""
                UPDATE game_identity
                SET match_confidence = :conf,
                    match_method = :method,
                    needs_manual_review = 0
                WHERE identity_id = :id
            """), {"conf": conf, "method": method, "id": id_b})
            matched_count += 1

        # Mark low-confidence singletons for manual review if they're in a
        # source that has cross-source candidates
        if match_pairs:
            matched_ids = set()
            for id_a, id_b, _, _ in match_pairs:
                matched_ids.add(id_a)
                matched_ids.add(id_b)

            for src_name, records in by_source.items():
                for rec in records:
                    if rec["identity_id"] not in matched_ids:
                        conn.execute(text("""
                            UPDATE game_identity
                            SET needs_manual_review = 1
                            WHERE identity_id = :id
                        """), {"id": rec["identity_id"]})
                        manual_review_count += 1

    total_matched = sum(stats.values())
    print("\n=== Matching Statistics ===")
    print(f"  Total cross-source pairs compared : {total_pairs:,}")
    print(f"  Pairs matched                     : {total_matched:,}")
    print(f"  Pairs below threshold             : {below_threshold:,}")
    print(f"  Manual review flagged            : {manual_review_count:,}")
    print("\n  Breakdown by method:")
    for method in ["exact_title_year", "exact_title_dev", "fuzzy_title_year",
                    "fuzzy_title_platform", "fuzzy_title_dev"]:
        count = stats.get(method, 0)
        print(f"    {method:30s}: {count:,}")
    print("===========================\n")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"[match_games] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
