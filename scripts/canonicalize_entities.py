"""Canonicalize multi-source entities after imports.

The static site expects one game page per real game and one source page per real
media outlet. Importers can temporarily create parallel IDs, so this step folds
obvious duplicates into canonical rows before metrics, weights, scores, and JSON
exports are computed.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from config import DB_PATH, ensure_dirs
from source_identity import canonical_source_name, source_id_for_name

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


GAME_METADATA_FIELDS = [
    "title_original",
    "release_date",
    "release_year",
    "developer",
    "publisher",
    "genres",
    "platforms",
    "description",
]

ROMAN_NUMERAL_TOKENS = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
    "xi": "11",
    "xii": "12",
    "xiii": "13",
    "xiv": "14",
    "xv": "15",
    "xvi": "16",
}
TRAILING_PLATFORM_TAG_RE = re.compile(
    r"\s*\((?:"
    r"ps[1-5]|playstation(?: [1-5])?|"
    r"xbox(?: one| 360| series x/s)?|"
    r"switch|wii u?|3ds|ds|pc|ios|android|vita|psp"
    r")\)\s*$",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_title(title: str) -> str:
    text = TRAILING_PLATFORM_TAG_RE.sub("", str(title or ""))
    text = text.replace("&", " and ")
    ascii_title = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    lowered = ascii_title.lower()
    alnum = re.sub(r"[^a-z0-9\s]", " ", lowered)
    normalized = re.sub(r"\s+", " ", alnum).strip()
    tokens = [ROMAN_NUMERAL_TOKENS.get(token, token) for token in normalized.split()]
    return " ".join(tokens)


def _url_slug_text(url: str | None) -> str:
    if not url:
        return ""
    path = urlparse(str(url)).path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1].replace("-", " ")


def _baseline_title_match_score(title: str | None, source_url: str | None) -> float:
    title_words = set(_normalize_title(str(title or "")).split())
    slug_words = [word for word in _normalize_title(_url_slug_text(source_url)).split() if word]
    if not title_words or not slug_words:
        return 0.0
    matched = sum(1 for word in slug_words if word in title_words)
    return matched / len(slug_words)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run init_db.py first.")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
    except (TypeError, json.JSONDecodeError):
        pass
    return [part.strip() for part in str(raw).split("|") if part.strip()]


def _merge_json_lists(values: list[str | None]) -> str | None:
    merged: list[str] = []
    for raw in values:
        for item in _parse_json_list(raw):
            if item not in merged:
                merged.append(item)
    return json.dumps(merged, ensure_ascii=False) if merged else None


def _best_scalar(values: list[object]) -> object | None:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _choose_canonical_game(conn: sqlite3.Connection, game_ids: list[str]) -> str:
    placeholders = ",".join("?" for _ in game_ids)
    rows = conn.execute(
        f"""
        SELECT g.game_id,
               SUM(CASE WHEN r.data_source='metacritic_kaggle' THEN 1 ELSE 0 END) AS mc_reviews,
               COUNT(r.review_id) AS review_count,
               MIN(g.created_at) AS created_at
        FROM games g
        LEFT JOIN reviews r ON r.game_id = g.game_id
        WHERE g.game_id IN ({placeholders})
        GROUP BY g.game_id
        """,
        game_ids,
    ).fetchall()
    ranked = sorted(
        rows,
        key=lambda r: (
            0 if str(r["game_id"]).startswith("mc-") else 1,
            -(r["mc_reviews"] or 0),
            -(r["review_count"] or 0),
            str(r["created_at"] or ""),
            str(r["game_id"]),
        ),
    )
    return ranked[0]["game_id"]


def _update_game_metadata(conn: sqlite3.Connection, canonical_id: str, duplicate_ids: list[str]) -> None:
    all_ids = [canonical_id, *duplicate_ids]
    placeholders = ",".join("?" for _ in all_ids)
    rows = conn.execute(
        f"SELECT * FROM games WHERE game_id IN ({placeholders})",
        all_ids,
    ).fetchall()
    if not rows:
        return

    by_id = {row["game_id"]: row for row in rows}
    ordered = [by_id[canonical_id], *[by_id[gid] for gid in duplicate_ids if gid in by_id]]
    updates = {}
    for field in GAME_METADATA_FIELDS:
        if field in {"genres", "platforms"}:
            updates[field] = _merge_json_lists([row[field] for row in ordered])
        else:
            updates[field] = _best_scalar([row[field] for row in ordered])
    updates["updated_at"] = _now()

    conn.execute(
        """
        UPDATE games
        SET title_original=?, release_date=?, release_year=?, developer=?, publisher=?,
            genres=?, platforms=?, description=?, updated_at=?
        WHERE game_id=?
        """,
        (
            updates["title_original"],
            updates["release_date"],
            updates["release_year"],
            updates["developer"],
            updates["publisher"],
            updates["genres"],
            updates["platforms"],
            updates["description"],
            updates["updated_at"],
            canonical_id,
        ),
    )


def canonicalize_sources(conn: sqlite3.Connection) -> int:
    rows = conn.execute("SELECT * FROM sources").fetchall()
    by_target: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        canonical_name = canonical_source_name(row["name"])
        by_target[source_id_for_name(canonical_name)].append(row)

    merged = 0
    for target_id, source_rows in by_target.items():
        canonical_name = canonical_source_name(source_rows[0]["name"])
        existing_ids = [row["source_id"] for row in source_rows]

        if target_id not in existing_ids:
            seed = source_rows[0]
            conn.execute(
                """
                INSERT OR IGNORE INTO sources
                (source_id, name, source_type, country_region, language, website_url,
                 is_institutional, is_individual_creator, inclusion_status, notes,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    canonical_name,
                    seed["source_type"],
                    seed["country_region"],
                    seed["language"],
                    seed["website_url"],
                    seed["is_institutional"],
                    seed["is_individual_creator"],
                    seed["inclusion_status"],
                    seed["notes"],
                    seed["created_at"],
                    _now(),
                ),
            )

        for row in source_rows:
            old_id = row["source_id"]
            if old_id == target_id:
                conn.execute(
                    "UPDATE sources SET name=?, updated_at=? WHERE source_id=?",
                    (canonical_name, _now(), target_id),
                )
                continue

            conn.execute("UPDATE reviews SET source_id=? WHERE source_id=?", (target_id, old_id))
            if _table_exists(conn, "reviewers"):
                conn.execute("UPDATE reviewers SET source_id=? WHERE source_id=?", (target_id, old_id))
            conn.execute("DELETE FROM source_metrics WHERE source_id=?", (old_id,))
            conn.execute("DELETE FROM weights WHERE source_id=?", (old_id,))
            conn.execute("DELETE FROM sources WHERE source_id=?", (old_id,))
            merged += 1

    return merged


def _candidate_game_groups(conn: sqlite3.Connection) -> list[list[str]]:
    groups: list[list[str]] = []
    rows = conn.execute(
        """
        SELECT game_id, title, release_year
        FROM games
        WHERE title IS NOT NULL
        """
    ).fetchall()

    exact_by_title_year: dict[tuple[str, int], list[str]] = defaultdict(list)
    title_only: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        norm = _normalize_title(row["title"])
        if not norm:
            continue
        title_only[norm].append(row)
        if row["release_year"] is not None:
            exact_by_title_year[(norm, int(row["release_year"]))].append(row["game_id"])

    for ids in exact_by_title_year.values():
        unique = sorted(set(ids))
        if len(unique) > 1:
            groups.append(unique)

    # If the title is exact and all known years agree, merge no-year records into
    # the same group. Avoid merging reboots with different release years.
    for same_title_rows in title_only.values():
        known_years = {int(row["release_year"]) for row in same_title_rows if row["release_year"] is not None}
        ids = sorted({row["game_id"] for row in same_title_rows})
        if len(ids) > 1 and len(known_years) <= 1:
            groups.append(ids)

    # Deduplicate overlapping groups.
    merged_sets: list[set[str]] = []
    for group in groups:
        group_set = set(group)
        absorbed = False
        for existing in merged_sets:
            if existing & group_set:
                existing |= group_set
                absorbed = True
                break
        if not absorbed:
            merged_sets.append(group_set)
    return [sorted(group) for group in merged_sets if len(group) > 1]


def _update_game_references(conn: sqlite3.Connection, old_id: str, canonical_id: str) -> None:
    direct_game_id_tables = [
        "reviews",
        "review_targets",
        "game_identity",
        "external_baseline",
        "score_snapshots",
    ]
    for table in direct_game_id_tables:
        if _table_exists(conn, table):
            conn.execute(f"UPDATE {table} SET game_id=? WHERE game_id=?", (canonical_id, old_id))

    if _table_exists(conn, "game_matches"):
        columns = _table_columns(conn, "game_matches")
        for column in ["game_id", "source_game_id", "target_game_id", "left_game_id", "right_game_id"]:
            if column in columns:
                conn.execute(f"UPDATE game_matches SET {column}=? WHERE {column}=?", (canonical_id, old_id))


def canonicalize_games(conn: sqlite3.Connection) -> int:
    merged = 0
    for group in _candidate_game_groups(conn):
        canonical_id = _choose_canonical_game(conn, group)
        duplicate_ids = [gid for gid in group if gid != canonical_id]
        if not duplicate_ids:
            continue

        _update_game_metadata(conn, canonical_id, duplicate_ids)
        for old_id in duplicate_ids:
            _update_game_references(conn, old_id, canonical_id)
            conn.execute("DELETE FROM games WHERE game_id=?", (old_id,))
            merged += 1

    return merged


def dedupe_external_baselines(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "external_baseline"):
        return 0

    removed = 0

    groups = conn.execute(
        """
        SELECT game_id,
               COALESCE(source_platform, '') AS platform_key,
               COUNT(*) AS c
        FROM external_baseline
        GROUP BY game_id, platform_key
        HAVING c > 1
        """
    ).fetchall()

    for group in groups:
        rows = conn.execute(
            """
            SELECT *
            FROM external_baseline
            WHERE game_id = ?
              AND COALESCE(source_platform, '') = ?
            """,
            (group["game_id"], group["platform_key"]),
        ).fetchall()
        ranked = sorted(
            rows,
            key=lambda row: (
                row["review_count"] is not None,
                row["review_count"] or -1,
                row["external_score"] is not None,
                row["external_score"] or -1,
                row["collected_at"] or "",
                row["baseline_id"],
            ),
            reverse=True,
        )
        keep_id = ranked[0]["baseline_id"]
        delete_ids = [row["baseline_id"] for row in ranked[1:]]
        if delete_ids:
            conn.execute(
                f"DELETE FROM external_baseline WHERE baseline_id IN ({','.join('?' for _ in delete_ids)})",
                delete_ids,
            )
            removed += len(delete_ids)

    url_groups = conn.execute(
        """
        SELECT COALESCE(data_source, '') AS data_source_key,
               COALESCE(source_platform, '') AS platform_key,
               source_url,
               COUNT(DISTINCT game_id) AS c
        FROM external_baseline
        WHERE source_url IS NOT NULL AND TRIM(source_url) != ''
        GROUP BY data_source_key, platform_key, source_url
        HAVING c > 1
        """
    ).fetchall()

    for group in url_groups:
        rows = conn.execute(
            """
            SELECT eb.*, g.title
            FROM external_baseline eb
            JOIN games g ON g.game_id = eb.game_id
            WHERE COALESCE(eb.data_source, '') = ?
              AND COALESCE(eb.source_platform, '') = ?
              AND eb.source_url = ?
            """,
            (group["data_source_key"], group["platform_key"], group["source_url"]),
        ).fetchall()
        ranked = sorted(
            rows,
            key=lambda row: (
                _baseline_title_match_score(row["title"], row["source_url"]),
                row["review_count"] is not None,
                row["review_count"] or -1,
                row["external_score"] is not None,
                row["external_score"] or -1,
                row["collected_at"] or "",
                row["baseline_id"],
            ),
            reverse=True,
        )
        delete_ids = [row["baseline_id"] for row in ranked[1:]]
        if delete_ids:
            conn.execute(
                f"DELETE FROM external_baseline WHERE baseline_id IN ({','.join('?' for _ in delete_ids)})",
                delete_ids,
            )
            removed += len(delete_ids)

    return removed


def dedupe_game_identities(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "game_identity"):
        return 0

    groups = conn.execute(
        """
        SELECT game_id,
               COALESCE(source_name, '') AS source_key,
               COALESCE(external_id, '') AS external_key,
               COUNT(*) AS c
        FROM game_identity
        GROUP BY game_id, source_key, external_key
        HAVING c > 1
        """
    ).fetchall()

    removed = 0
    for group in groups:
        rows = conn.execute(
            """
            SELECT *
            FROM game_identity
            WHERE game_id = ?
              AND COALESCE(source_name, '') = ?
              AND COALESCE(external_id, '') = ?
            """,
            (group["game_id"], group["source_key"], group["external_key"]),
        ).fetchall()
        ranked = sorted(
            rows,
            key=lambda row: (
                row["match_confidence"] or 0,
                row["external_url"] is not None,
                row["external_slug"] is not None,
                row["updated_at"] or "",
                row["identity_id"],
            ),
            reverse=True,
        )
        delete_ids = [row["identity_id"] for row in ranked[1:]]
        if delete_ids:
            conn.execute(
                f"DELETE FROM game_identity WHERE identity_id IN ({','.join('?' for _ in delete_ids)})",
                delete_ids,
            )
            removed += len(delete_ids)

    return removed


def dedupe_cross_source_reviews(conn: sqlite3.Connection) -> int:
    """Drop MC rows already covered by an OpenCritic row for same game/source.

    Metacritic's historical snapshot is useful as a base, but for popular games
    it overlaps heavily with OpenCritic. When the same media outlet has the same
    normalized score in both sources, keep the OpenCritic row because it usually
    carries URL/date/platform provenance, and remove the older MC duplicate so
    aggregate scores count one outlet review once.
    """
    if not _table_exists(conn, "reviews"):
        return 0

    oc_scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in conn.execute(
        """
        SELECT game_id, source_id, normalized_score
        FROM reviews
        WHERE data_source = 'opencritic_web'
          AND normalized_score IS NOT NULL
        """
    ):
        oc_scores[(row["game_id"], row["source_id"])].append(float(row["normalized_score"]))

    delete_ids: list[str] = []
    for row in conn.execute(
        """
        SELECT review_id, game_id, source_id, normalized_score
        FROM reviews
        WHERE data_source = 'metacritic_kaggle'
          AND normalized_score IS NOT NULL
        """
    ):
        scores = oc_scores.get((row["game_id"], row["source_id"]))
        if not scores:
            continue
        mc_score = float(row["normalized_score"])
        if any(abs(mc_score - oc_score) <= 0.51 for oc_score in scores):
            delete_ids.append(row["review_id"])

    for start in range(0, len(delete_ids), 500):
        chunk = delete_ids[start:start + 500]
        conn.execute(
            f"DELETE FROM reviews WHERE review_id IN ({','.join('?' for _ in chunk)})",
            chunk,
        )
    return len(delete_ids)


def print_audit(conn: sqlite3.Connection) -> None:
    duplicate_sources = conn.execute(
        """
        SELECT lower(name) AS key, COUNT(*) AS c
        FROM sources
        GROUP BY lower(name)
        HAVING c > 1
        ORDER BY c DESC, key
        LIMIT 10
        """
    ).fetchall()
    duplicate_games = _candidate_game_groups(conn)[:10]
    duplicate_baselines = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM (
            SELECT game_id, COALESCE(source_platform, '') AS platform_key
            FROM external_baseline
            GROUP BY game_id, platform_key
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()["c"] if _table_exists(conn, "external_baseline") else 0
    duplicate_baseline_urls = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM (
            SELECT COALESCE(data_source, '') AS data_source_key,
                   COALESCE(source_platform, '') AS platform_key,
                   source_url
            FROM external_baseline
            WHERE source_url IS NOT NULL AND TRIM(source_url) != ''
            GROUP BY data_source_key, platform_key, source_url
            HAVING COUNT(DISTINCT game_id) > 1
        )
        """
    ).fetchone()["c"] if _table_exists(conn, "external_baseline") else 0
    duplicate_identities = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM (
            SELECT game_id, COALESCE(source_name, '') AS source_key,
                   COALESCE(external_id, '') AS external_key
            FROM game_identity
            GROUP BY game_id, source_key, external_key
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()["c"] if _table_exists(conn, "game_identity") else 0
    print("[canonicalize] Duplicate source names remaining:", len(duplicate_sources))
    for row in duplicate_sources:
        print(f"  source '{row['key']}': {row['c']}")
    print("[canonicalize] Exact duplicate game groups remaining:", len(duplicate_games))
    for group in duplicate_games:
        titles = conn.execute(
            f"SELECT game_id, title, release_year FROM games WHERE game_id IN ({','.join('?' for _ in group)})",
            group,
        ).fetchall()
        print("  " + " | ".join(f"{row['game_id']}:{row['title']} ({row['release_year']})" for row in titles))
    print("[canonicalize] Duplicate external baseline groups remaining:", duplicate_baselines)
    print("[canonicalize] Duplicate external baseline URLs remaining:", duplicate_baseline_urls)
    print("[canonicalize] Duplicate game identity groups remaining:", duplicate_identities)


def run() -> None:
    ensure_dirs()
    conn = _connect()
    try:
        with conn:
            source_merges = canonicalize_sources(conn)
            game_merges = canonicalize_games(conn)
            review_dedupes = dedupe_cross_source_reviews(conn)
            baseline_dedupes = dedupe_external_baselines(conn)
            identity_dedupes = dedupe_game_identities(conn)

        print(f"[canonicalize] Source rows merged: {source_merges}")
        print(f"[canonicalize] Game rows merged:   {game_merges}")
        print(f"[canonicalize] Cross-source review rows removed: {review_dedupes}")
        print(f"[canonicalize] Baseline rows removed: {baseline_dedupes}")
        print(f"[canonicalize] Identity rows removed: {identity_dedupes}")
        print_audit(conn)
    finally:
        conn.close()


def main() -> None:
    try:
        run()
    except Exception as exc:
        print(f"[canonicalize] ERROR: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
