"""Export all IMS Games data from SQLite to static JSON files for the frontend.

OPTIMIZED: uses bulk queries + in-memory grouping instead of per-game queries.
"""

import json
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

from config import ALGORITHM_VERSION, DB_PATH, SITE_DATA_DIR, ensure_dirs


def connect_db():
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def write_json(path, data):
    from pathlib import Path as P
    p = P(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_json_text(raw):
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, (list, dict)) else [result]
    except (json.JSONDecodeError, TypeError):
        return [s.strip() for s in str(raw).split("|") if s.strip()]


# ---------------------------------------------------------------------------
# 1. games.json
# ---------------------------------------------------------------------------
def export_games_list(conn):
    rows = conn.execute("""
        SELECT g.game_id, g.title, g.release_year, g.developer, g.publisher,
               g.genres, g.platforms, g.release_date,
               ss.raw_average, ss.trimmed_mean, ss.calibrated_score,
               ss.weighted_score, ss.sample_count,
               eb.external_score AS mc_score
        FROM games g
        LEFT JOIN score_snapshots ss ON ss.game_id = g.game_id AND ss.algorithm_version = ?
        LEFT JOIN external_baseline eb ON eb.game_id = g.game_id AND eb.source_platform = 'metacritic'
        ORDER BY g.title
    """, (ALGORITHM_VERSION,)).fetchall()

    games = []
    for r in rows:
        genres = _parse_json_text(r["genres"])
        platforms = _parse_json_text(r["platforms"])
        release_year = r["release_year"]
        if release_year is None and r["release_date"]:
            try:
                release_year = int(str(r["release_date"])[:4])
            except (ValueError, TypeError):
                pass

        games.append({
            "game_id": r["game_id"],
            "title": r["title"],
            "release_year": release_year,
            "developer": r["developer"],
            "publisher": r["publisher"],
            "genres": genres if isinstance(genres, list) else [],
            "platforms": platforms if isinstance(platforms, list) else [],
            "metacritic_score": r["mc_score"],
            "opencritic_score": None,
            "ims_raw": r["raw_average"],
            "ims_robust": r["trimmed_mean"],
            "ims_calibrated": r["calibrated_score"],
            "ims_weighted": r["weighted_score"],
            "review_count": r["sample_count"] or 0,
            "has_enhanced_data": bool(genres or platforms or r["developer"]),
        })

    out = SITE_DATA_DIR / "games.json"
    write_json(out, games)
    print(f"  [OK] games.json  ({len(games)} games)")
    return games


# ---------------------------------------------------------------------------
# 2. games/{game_id}.json — BULK optimized
# ---------------------------------------------------------------------------
def export_game_details(conn, games):
    # Bulk load ALL reviews with source names
    print("  [INFO] Bulk loading reviews...")
    all_reviews = conn.execute("""
        SELECT r.game_id, r.review_id, s.name AS source_name, r.source_id,
               r.normalized_score, r.original_score_value, r.original_score,
               r.review_url, r.review_date, r.language, r.platform,
               r.summary, r.positive_points, r.negative_points,
               r.data_source, r.provenance_url
        FROM reviews r
        LEFT JOIN sources s ON s.source_id = r.source_id
        ORDER BY r.review_date DESC
    """).fetchall()

    reviews_by_game = defaultdict(list)
    for r in all_reviews:
        reviews_by_game[r["game_id"]].append(r)

    # Bulk load ALL source metrics
    sm_rows = conn.execute("""
        SELECT source_id, sample_count, mean_score, score_std,
               score_bias, discrimination_power, genre_coverage, platform_coverage
        FROM source_metrics WHERE algorithm_version = ?
    """, (ALGORITHM_VERSION,)).fetchall()
    sm_lookup = {}
    for r in sm_rows:
        sm_lookup[r["source_id"]] = {
            "sample_count": r["sample_count"],
            "mean_score": r["mean_score"],
            "score_std": r["score_std"],
            "score_bias": r["score_bias"],
            "discrimination_power": r["discrimination_power"],
            "genre_coverage": _parse_json_text(r["genre_coverage"]),
            "platform_coverage": _parse_json_text(r["platform_coverage"]),
        }

    # Bulk load ALL external baselines
    bl_rows = conn.execute("""
        SELECT game_id, source_platform, external_score, external_user_score,
               review_count, source_url, data_source
        FROM external_baseline
    """).fetchall()
    bl_by_game = defaultdict(list)
    for r in bl_rows:
        bl_by_game[r["game_id"]].append({
            "source_platform": r["source_platform"],
            "external_score": r["external_score"],
            "external_user_score": r["external_user_score"],
            "review_count": r["review_count"],
            "source_url": r["source_url"],
            "data_source": r["data_source"],
        })

    # Bulk load weights with explanations
    w_rows = conn.execute("""
        SELECT source_id, genre, platform, context_weight, explanation
        FROM weights WHERE algorithm_version = ?
    """, (ALGORITHM_VERSION,)).fetchall()
    w_lookup = {}
    for r in w_rows:
        w_lookup[(r["source_id"], r["genre"], r["platform"])] = {
            "weight": r["context_weight"],
            "explanation": r["explanation"],
        }

    print(f"  [INFO] Writing {len(games)} detail files...")
    count = 0
    for game in games:
        gid = game["game_id"]

        # Reviews
        game_reviews = reviews_by_game.get(gid, [])
        reviews_out = []
        source_ids_in_game = set()
        lang_dist = defaultdict(int)
        plat_dist = defaultdict(int)

        for rv in game_reviews:
            sid = rv["source_id"]
            source_ids_in_game.add(sid)

            # Find weight for this source + game genre/platform
            w_info = w_lookup.get((sid, None, None), {})
            weight_val = w_info.get("weight")
            weight_expl = w_info.get("explanation")

            reviews_out.append({
                "source_name": rv["source_name"],
                "reviewer": None,
                "score": rv["normalized_score"],
                "raw_score": rv["original_score_value"],
                "weight": weight_val,
                "weight_explanation": weight_expl,
                "url": rv["review_url"],
                "date": rv["review_date"],
                "language": rv["language"],
                "platform": rv["platform"],
                "summary": rv["summary"],
                "positive_points": rv["positive_points"],
                "negative_points": rv["negative_points"],
            })

            if rv["language"]:
                lang_dist[rv["language"]] += 1
            if rv["platform"]:
                plat_dist[rv["platform"]] += 1

        # Source metrics
        source_metrics = {}
        for sid in source_ids_in_game:
            if sid in sm_lookup:
                source_metrics[sid] = sm_lookup[sid]

        detail = {
            **game,
            "reviews": reviews_out,
            "source_metrics": source_metrics,
            "external_baselines": bl_by_game.get(gid, []),
            "language_distribution": dict(lang_dist),
            "platform_distribution": dict(plat_dist),
        }

        out = SITE_DATA_DIR / "games" / f"{gid}.json"
        write_json(out, detail)
        count += 1

        if count % 2000 == 0:
            print(f"    ... {count} files written")

    print(f"  [OK] games/{{id}}.json  ({count} detail files)")


# ---------------------------------------------------------------------------
# 3. sources.json
# ---------------------------------------------------------------------------
def export_sources_list(conn):
    rows = conn.execute("""
        SELECT s.source_id, s.name, s.source_type, s.language, s.country_region,
               sm.sample_count, sm.mean_score
        FROM sources s
        LEFT JOIN source_metrics sm ON sm.source_id = s.source_id AND sm.algorithm_version = ?
        ORDER BY s.name
    """, (ALGORITHM_VERSION,)).fetchall()

    # Weight averages
    w_avg = {}
    for r in conn.execute("""
        SELECT source_id, AVG(context_weight) AS avg_w
        FROM weights WHERE algorithm_version = ? GROUP BY source_id
    """, (ALGORITHM_VERSION,)).fetchall():
        w_avg[r["source_id"]] = r["avg_w"]

    # Review count fallback
    rc_map = {}
    for r in conn.execute("SELECT source_id, COUNT(*) AS c FROM reviews GROUP BY source_id"):
        rc_map[r["source_id"]] = r["c"]

    sources = []
    for r in rows:
        sid = r["source_id"]
        sources.append({
            "source_id": sid,
            "name": r["name"],
            "source_type": r["source_type"],
            "language": r["language"],
            "country_region": r["country_region"],
            "review_count": r["sample_count"] or rc_map.get(sid, 0),
            "mean_score": r["mean_score"],
            "base_weight": w_avg.get(sid),
        })

    out = SITE_DATA_DIR / "sources.json"
    write_json(out, sources)
    print(f"  [OK] sources.json  ({len(sources)} sources)")
    return sources


# ---------------------------------------------------------------------------
# 4. sources/{source_id}.json — BULK optimized
# ---------------------------------------------------------------------------
def export_source_details(conn, sources):
    # Bulk load reviews grouped by source
    print("  [INFO] Bulk loading source reviews...")
    rev_rows = conn.execute("""
        SELECT r.source_id, g.title AS game_title, g.game_id,
               r.normalized_score, r.review_url, r.review_date
        FROM reviews r
        JOIN games g ON g.game_id = r.game_id
        ORDER BY r.review_date DESC
    """).fetchall()

    reviews_by_source = defaultdict(list)
    for r in rev_rows:
        reviews_by_source[r["source_id"]].append(r)

    # Bulk load genre/platform coverage per source from reviews+games
    gc_rows = conn.execute("""
        SELECT r.source_id, g.genres, g.platforms
        FROM reviews r
        JOIN games g ON g.game_id = r.game_id
        WHERE g.genres IS NOT NULL OR g.platforms IS NOT NULL
    """).fetchall()
    genre_cov = defaultdict(lambda: defaultdict(int))
    plat_cov = defaultdict(lambda: defaultdict(int))
    for r in gc_rows:
        sid = r["source_id"]
        if r["genres"]:
            for g in _parse_json_text(r["genres"]):
                if isinstance(g, str) and g.strip():
                    genre_cov[sid][g.strip()] += 1
        if r["platforms"]:
            for p in _parse_json_text(r["platforms"]):
                if isinstance(p, str) and p.strip():
                    plat_cov[sid][p.strip()] += 1

    count = 0
    for src in sources:
        sid = src["source_id"]

        # Metrics
        metrics = {}
        sm = conn.execute("""
            SELECT sample_count, mean_score, score_std, score_bias,
                   discrimination_power, genre_coverage, platform_coverage
            FROM source_metrics WHERE source_id = ? AND algorithm_version = ? LIMIT 1
        """, (sid, ALGORITHM_VERSION)).fetchone()
        if sm:
            metrics = {k: sm[k] for k in sm.keys() if k not in ("genre_coverage", "platform_coverage")}
            metrics["genre_coverage"] = _parse_json_text(sm["genre_coverage"])
            metrics["platform_coverage"] = _parse_json_text(sm["platform_coverage"])

        # Weights
        w_list = []
        for wr in conn.execute("""
            SELECT genre, platform, base_weight, context_weight,
                   confidence, explanation
            FROM weights WHERE source_id = ? AND algorithm_version = ?
        """, (sid, ALGORITHM_VERSION)).fetchall():
            w_list.append(dict(wr))
        weights = {"records": w_list} if w_list else {}

        # Recent reviews (limit 20)
        recent = reviews_by_source.get(sid, [])[:20]
        recent_reviews = [{
            "game_title": r["game_title"],
            "game_id": r["game_id"],
            "score": r["normalized_score"],
            "url": r["review_url"],
            "date": r["review_date"],
        } for r in recent]

        detail = {
            **src,
            "metrics": metrics,
            "weights": weights,
            "recent_reviews": recent_reviews,
            "genre_coverage": dict(genre_cov.get(sid, {})),
            "platform_coverage": dict(plat_cov.get(sid, {})),
        }

        out = SITE_DATA_DIR / "sources" / f"{sid}.json"
        write_json(out, detail)
        count += 1

    print(f"  [OK] sources/{{id}}.json  ({count} detail files)")


# ---------------------------------------------------------------------------
# 5. scores/latest.json
# ---------------------------------------------------------------------------
def export_latest_scores(conn):
    total_games = conn.execute(
        "SELECT COUNT(DISTINCT game_id) AS c FROM score_snapshots"
    ).fetchone()["c"]
    total_reviews = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]

    data = {
        "algorithm_version": ALGORITHM_VERSION,
        "total_games_scored": total_games,
        "total_reviews": total_reviews,
        "date": datetime.now(timezone.utc).isoformat(),
    }
    out = SITE_DATA_DIR / "scores" / "latest.json"
    write_json(out, data)
    print(f"  [OK] scores/latest.json")


# ---------------------------------------------------------------------------
# 6. meta.json
# ---------------------------------------------------------------------------
def export_meta(conn):
    total_games = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
    total_sources = conn.execute("SELECT COUNT(*) AS c FROM sources").fetchone()["c"]
    total_reviews = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]

    ds_rows = conn.execute(
        "SELECT DISTINCT data_source FROM reviews WHERE data_source IS NOT NULL"
    ).fetchall()
    ds_info = [{"name": r["data_source"], "type": "critic_reviews"} for r in ds_rows]
    if not ds_info:
        ds_info = [{"name": "Metacritic", "type": "critic_reviews"},
                    {"name": "OpenCritic", "type": "critic_reviews"}]

    meta = {
        "algorithm_version": ALGORITHM_VERSION,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_games": total_games,
        "total_sources": total_sources,
        "total_reviews": total_reviews,
        "data_sources": ds_info,
    }
    out = SITE_DATA_DIR / "meta.json"
    write_json(out, meta)
    print(f"  [OK] meta.json")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    print("=" * 60)
    print("  IMS Games  -  Export Static JSON")
    print("=" * 60)

    ensure_dirs()
    for sub in ("games", "sources", "scores"):
        (SITE_DATA_DIR / sub).mkdir(parents=True, exist_ok=True)

    conn = connect_db()
    try:
        print("\n[1/6] Exporting games list...")
        games = export_games_list(conn)
        print("[2/6] Exporting game detail pages...")
        export_game_details(conn, games)
        print("[3/6] Exporting sources list...")
        sources = export_sources_list(conn)
        print("[4/6] Exporting source detail pages...")
        export_source_details(conn, sources)
        print("[5/6] Exporting latest scores...")
        export_latest_scores(conn)
        print("[6/6] Exporting meta...")
        export_meta(conn)
    finally:
        conn.close()

    elapsed = time.time() - t0
    file_count = sum(1 for _ in SITE_DATA_DIR.rglob("*.json"))
    total_bytes = sum(p.stat().st_size for p in SITE_DATA_DIR.rglob("*.json"))

    def fmt(b):
        return f"{b / (1024*1024):.1f} MB" if b > 1024*1024 else f"{b/1024:.1f} KB"

    print(f"\n  Files: {file_count}, Size: {fmt(total_bytes)}, Time: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
