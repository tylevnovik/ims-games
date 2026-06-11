"""Repair Metacritic-backed reviews and metadata from public web JSON.

The Kaggle Metacritic snapshot used by this project often caps well-known games
at exactly 50 critic rows. This importer targets those existing games, fetches
Metacritic's public JSON endpoints by title slug, verifies title/year matches,
and replaces the capped Kaggle rows for that game with the fuller web review
set. It can also fill missing release-year metadata for high-confidence modern
games by reading the Metacritic product endpoint without importing reviews.

Usage:
    python import_metacritic_web.py --list-only --limit 30
    python import_metacritic_web.py --write --limit 30
    python import_metacritic_web.py --write --target-sample-counts 50 100
    python import_metacritic_web.py --metadata-missing-years --write
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPException, IncompleteRead
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from config import ALGORITHM_VERSION, DB_PATH, DATA_DIR, ensure_dirs
from source_identity import canonical_source_name, source_id_for_name

BASE_URL = "https://www.metacritic.com"
BACKEND_URL = "https://backend.metacritic.com"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; IMS-Games-Backfill/0.1)"
METACRITIC_WEB_DIR = DATA_DIR / "metacritic" / "web-cache"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _truncate(value: object, max_len: int = 2000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text if len(text) <= max_len else text[: max_len - 1] + "..."


def _year_from_date(value: object) -> int | None:
    if not value:
        return None
    match = re.match(r"(\d{4})", str(value))
    return int(match.group(1)) if match else None


def _paren_year(title: str) -> int | None:
    match = re.search(r"\((\d{4})\)\s*$", str(title or ""))
    return int(match.group(1)) if match else None


def _ascii_text(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _slugify(title: str) -> str:
    text = _ascii_text(title).lower()
    text = text.replace("&", " and ")
    text = text.replace("+", " plus ")
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return re.sub(r"-+", "-", text)


def _normalize_title(title: str) -> str:
    text = re.sub(r"\s*\([^)]+\)\s*$", "", str(title or ""))
    text = _ascii_text(text).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _slug_candidates(title: str, manual_slug: str | None = None) -> list[str]:
    candidates: list[str] = []
    if manual_slug:
        candidates.append(manual_slug.strip("/ "))

    full_slug = _slugify(title)
    stripped_title = re.sub(r"\s*\((\d{4})\)\s*$", "", str(title or "")).strip()
    stripped_slug = _slugify(stripped_title)
    full_slug_without_plus = _slugify(str(title or "").replace("+", " "))
    stripped_slug_without_plus = _slugify(stripped_title.replace("+", " "))
    colon_prefix = str(stripped_title or title or "").split(":", 1)[0].strip()
    colon_prefix_slug = _slugify(colon_prefix)
    featuring_prefix_slugs: list[str] = []
    for marker in (" featuring ", " feat. ", " feat "):
        lowered = f" {stripped_title.lower()} "
        if marker in lowered:
            prefix = stripped_title[: lowered.index(marker) - 1].strip()
            if prefix:
                featuring_prefix_slugs.append(_slugify(prefix))
    year = _paren_year(title)

    if year and stripped_slug:
        candidates.append(f"{stripped_slug}-{year}")
    if year and stripped_slug_without_plus:
        candidates.append(f"{stripped_slug_without_plus}-{year}")
    if full_slug:
        candidates.append(full_slug)
    if full_slug_without_plus:
        candidates.append(full_slug_without_plus)
    if stripped_slug:
        candidates.append(stripped_slug)
    if stripped_slug_without_plus:
        candidates.append(stripped_slug_without_plus)
    for slug in featuring_prefix_slugs:
        if slug:
            candidates.append(slug)
    if colon_prefix_slug and colon_prefix_slug not in {full_slug, stripped_slug}:
        candidates.append(colon_prefix_slug)

    unique: list[str] = []
    for slug in candidates:
        if slug and slug not in unique:
            unique.append(slug)
    return unique


def _review_id(game_id: str, item: dict) -> str:
    raw = "|".join(
        str(item.get(key) or "")
        for key in ("publicationSlug", "url", "date", "score", "quote")
    )
    return f"mcweb-rev-{game_id}-{_md5(raw)[:20]}"


def _baseline_id(game_id: str) -> str:
    return f"mcweb-bl-{game_id}"


def _identity_id(game_id: str) -> str:
    return f"mcweb-id-{game_id}"


class MetacriticWebClient:
    def __init__(
        self,
        cache_dir: Path,
        refresh_cache: bool,
        user_agent: str,
        sleep_seconds: float,
        retries: int,
        retry_backoff: float,
    ) -> None:
        self.cache_dir = cache_dir
        self.refresh_cache = refresh_cache
        self.user_agent = user_agent
        self.sleep_seconds = sleep_seconds
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_json(self, url: str) -> dict:
        cache_path = self.cache_dir / f"{_md5(url)}.json"
        if cache_path.exists() and not self.refresh_cache:
            return json.loads(cache_path.read_text(encoding="utf-8"))

        req = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/",
            },
        )
        max_attempts = max(1, self.retries + 1)
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                with urlopen(req, timeout=40) as response:
                    payload = json.loads(response.read().decode("utf-8", "replace"))
                cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                if self.sleep_seconds > 0:
                    time.sleep(self.sleep_seconds)
                return payload
            except HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get("Location")
                    if location:
                        redirect_url = urljoin(url, location)
                        if redirect_url != url:
                            return self.fetch_json(redirect_url)
                    raise
                if exc.code == 404:
                    raise
                if exc.code < 500 and exc.code not in (408, 429):
                    raise RuntimeError(f"Could not fetch {url}: {exc}") from exc
                last_exc = exc
            except (
                URLError,
                TimeoutError,
                ConnectionError,
                OSError,
                HTTPException,
                IncompleteRead,
                json.JSONDecodeError,
            ) as exc:
                last_exc = exc

            if attempt >= max_attempts:
                raise RuntimeError(f"Could not fetch {url}: {last_exc}") from last_exc

            wait = self.retry_backoff * (2 ** (attempt - 1))
            print(
                f"[metacritic_web] retry {attempt}/{max_attempts - 1}: {url} ({last_exc})",
                flush=True,
            )
            if wait > 0:
                time.sleep(wait)

        raise RuntimeError(f"Could not fetch {url}: {last_exc}")

    def fetch_product(self, slug: str) -> dict | None:
        url = (
            f"{BACKEND_URL}/games/metacritic/{quote(slug)}/web"
            "?componentName=product&componentDisplayName=Product&componentType=Product"
        )
        try:
            payload = self.fetch_json(url)
        except HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308, 404):
                return None
            raise
        return ((payload.get("data") or {}).get("item") or None)

    def fetch_reviews(self, slug: str, page_size: int, expected_count: int | None) -> list[dict]:
        reviews: list[dict] = []
        seen: set[str] = set()
        offset = 0
        limit = max(1, min(page_size, 100))

        while True:
            url = (
                f"{BACKEND_URL}/reviews/metacritic/critic/games/{quote(slug)}/web"
                f"?offset={offset}&limit={limit}&filterBySentiment=all&sort=score"
                "&componentName=critic-reviews&componentDisplayName=critic+Reviews"
                "&componentType=ReviewList"
            )
            payload = self.fetch_json(url)
            data = payload.get("data") or {}
            items = data.get("items") or []
            total = int(data.get("totalResults") or expected_count or 0)

            new_count = 0
            for item in items:
                raw_id = _md5(json.dumps(item, sort_keys=True, ensure_ascii=False))
                if raw_id in seen:
                    continue
                seen.add(raw_id)
                reviews.append(item)
                new_count += 1

            if not items or new_count == 0:
                break
            offset += len(items)
            if total and offset >= total:
                break

        return reviews


@dataclass
class TargetGame:
    game_id: str
    title: str
    release_year: int | None
    sample_count: int
    weighted_score: float | None
    opencritic_count: int
    metacritic_kaggle_count: int
    metacritic_web_count: int
    manual_slug: str | None = None


def connect_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}. Run init_db.py first.")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def load_targets(conn: sqlite3.Connection, args: argparse.Namespace) -> list[TargetGame]:
    if args.metadata_missing_years:
        return load_metadata_targets(conn, args)

    csv_targets = load_targets_csv(args.targets_csv) if args.targets_csv else {}

    placeholders = ",".join("?" for _ in args.target_sample_counts)
    params: list[object] = [ALGORITHM_VERSION]
    sample_clause = ""
    if args.target_sample_counts:
        sample_clause = f"AND ss.sample_count IN ({placeholders})"
        params.extend(args.target_sample_counts)

    rows = conn.execute(
        f"""
        SELECT g.game_id, g.title, g.release_year,
               ss.sample_count, ss.weighted_score,
               SUM(CASE WHEN r.data_source = 'opencritic_web' THEN 1 ELSE 0 END) AS opencritic_count,
               SUM(CASE WHEN r.data_source = 'metacritic_kaggle' THEN 1 ELSE 0 END) AS metacritic_kaggle_count,
               SUM(CASE WHEN r.data_source = 'metacritic_web' THEN 1 ELSE 0 END) AS metacritic_web_count
        FROM score_snapshots ss
        JOIN games g ON g.game_id = ss.game_id
        JOIN reviews r ON r.game_id = ss.game_id AND r.normalized_score IS NOT NULL
        WHERE ss.algorithm_version = ?
          {sample_clause}
        GROUP BY g.game_id
        HAVING metacritic_kaggle_count > 0
           AND (? = 0 OR opencritic_count = 0)
           AND (? = 0 OR metacritic_web_count = 0)
        ORDER BY ss.weighted_score DESC, g.title
        """,
        (*params, 1 if args.only_no_opencritic else 0, 1 if args.skip_existing_web else 0),
    ).fetchall()

    targets = [
        TargetGame(
            game_id=row["game_id"],
            title=row["title"],
            release_year=row["release_year"],
            sample_count=int(row["sample_count"] or 0),
            weighted_score=row["weighted_score"],
            opencritic_count=int(row["opencritic_count"] or 0),
            metacritic_kaggle_count=int(row["metacritic_kaggle_count"] or 0),
            metacritic_web_count=int(row["metacritic_web_count"] or 0),
            manual_slug=csv_targets.get(row["game_id"]) or csv_targets.get(row["title"]),
        )
        for row in rows
    ]
    if args.limit:
        targets = targets[: args.limit]
    return targets


def load_metadata_targets(conn: sqlite3.Connection, args: argparse.Namespace) -> list[TargetGame]:
    csv_targets = load_targets_csv(args.targets_csv) if args.targets_csv else {}
    params: list[object] = [
        ALGORITHM_VERSION,
        args.metadata_min_score,
        args.metadata_min_sample_count,
        1 if args.metadata_require_opencritic else 0,
        1 if args.metadata_skip_existing_identity else 0,
    ]
    rows = conn.execute(
        """
        SELECT g.game_id, g.title, g.release_year,
               ss.sample_count, ss.weighted_score,
               SUM(CASE WHEN r.data_source = 'opencritic_web' THEN 1 ELSE 0 END) AS opencritic_count,
               SUM(CASE WHEN r.data_source = 'metacritic_kaggle' THEN 1 ELSE 0 END) AS metacritic_kaggle_count,
               SUM(CASE WHEN r.data_source = 'metacritic_web' THEN 1 ELSE 0 END) AS metacritic_web_count,
               MAX(CASE WHEN gi.source_name = 'metacritic_web' THEN 1 ELSE 0 END) AS has_metacritic_identity
        FROM score_snapshots ss
        JOIN games g ON g.game_id = ss.game_id
        JOIN reviews r ON r.game_id = ss.game_id AND r.normalized_score IS NOT NULL
        LEFT JOIN game_identity gi ON gi.game_id = g.game_id
        WHERE ss.algorithm_version = ?
          AND g.release_year IS NULL
          AND ss.weighted_score >= ?
          AND ss.sample_count >= ?
        GROUP BY g.game_id
        HAVING (? = 0 OR opencritic_count > 0)
           AND (? = 0 OR has_metacritic_identity = 0)
        ORDER BY ss.weighted_score DESC, ss.sample_count DESC, g.title
        """,
        params,
    ).fetchall()

    targets = [
        TargetGame(
            game_id=row["game_id"],
            title=row["title"],
            release_year=row["release_year"],
            sample_count=int(row["sample_count"] or 0),
            weighted_score=row["weighted_score"],
            opencritic_count=int(row["opencritic_count"] or 0),
            metacritic_kaggle_count=int(row["metacritic_kaggle_count"] or 0),
            metacritic_web_count=int(row["metacritic_web_count"] or 0),
            manual_slug=csv_targets.get(row["game_id"]) or csv_targets.get(row["title"]),
        )
        for row in rows
    ]
    if args.limit:
        targets = targets[: args.limit]
    return targets


def load_targets_csv(path: str) -> dict[str, str]:
    result: dict[str, str] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            slug = (row.get("metacritic_slug") or row.get("slug") or "").strip()
            if not slug:
                continue
            for key_name in ("game_id", "title"):
                key = (row.get(key_name) or "").strip()
                if key:
                    result[key] = slug
    return result


def is_acceptable_product(target: TargetGame, product: dict, year_tolerance: int) -> tuple[bool, str]:
    product_title = str(product.get("title") or "")
    if _normalize_title(product_title) != _normalize_title(target.title):
        return False, f"title mismatch: {product_title!r}"

    product_year = product.get("premiereYear") or _year_from_date(product.get("releaseDate"))
    product_year = int(product_year) if product_year else None
    target_year = int(target.release_year) if target.release_year else None
    target_paren_year = _paren_year(target.title)

    if target_paren_year and product_year != target_paren_year:
        return False, f"version year mismatch: product={product_year}, target={target_paren_year}"

    if product_year and target_year:
        if abs(product_year - target_year) <= year_tolerance:
            return True, "title_year"
        if product_year < target_year and target_paren_year is None:
            return True, f"title_earlier_year_repair:{target_year}->{product_year}"
        return False, f"release year mismatch: product={product_year}, target={target_year}"

    return True, "title_only"


def find_product_for_target(
    client: MetacriticWebClient,
    target: TargetGame,
    year_tolerance: int,
) -> tuple[str | None, dict | None, str]:
    errors: list[str] = []
    for slug in _slug_candidates(target.title, target.manual_slug):
        product = client.fetch_product(slug)
        if not product:
            errors.append(f"{slug}:404")
            continue
        accepted, reason = is_acceptable_product(target, product, year_tolerance)
        if accepted:
            return slug, product, reason
        errors.append(f"{slug}:{reason}")
    return None, None, "; ".join(errors)


def upsert_source(conn: sqlite3.Connection, publication_name: str, now: str) -> str:
    source_name = canonical_source_name(publication_name or "Unknown Source")
    source_id = source_id_for_name(source_name)
    conn.execute(
        """
        INSERT INTO sources
        (source_id, name, source_type, country_region, language, website_url,
         is_institutional, is_individual_creator, inclusion_status, notes,
         created_at, updated_at)
        VALUES (?, ?, 'media', NULL, 'en', NULL, 1, 0, 'active',
                'Imported or linked from Metacritic public web snapshot', ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            name = COALESCE(sources.name, excluded.name),
            language = COALESCE(sources.language, excluded.language),
            updated_at = excluded.updated_at
        """,
        (source_id, source_name, now, now),
    )
    return source_id


def repair_game_metadata(
    conn: sqlite3.Connection,
    target: TargetGame,
    product: dict,
    now: str,
) -> None:
    product_year = product.get("premiereYear") or _year_from_date(product.get("releaseDate"))
    product_year = int(product_year) if product_year else None
    release_date = product.get("releaseDate")
    description = _truncate(product.get("description"))
    platform = product.get("platform")
    platform_json = json.dumps([platform], ensure_ascii=False) if platform else None

    conn.execute(
        """
        UPDATE games
        SET release_date = CASE
                WHEN ? IS NOT NULL
                 AND (release_year IS NULL OR ? <= release_year)
                THEN ?
                ELSE COALESCE(release_date, ?)
            END,
            release_year = CASE
                WHEN ? IS NOT NULL
                 AND (release_year IS NULL OR ? <= release_year)
                THEN ?
                ELSE COALESCE(release_year, ?)
            END,
            platforms = COALESCE(platforms, ?),
            description = COALESCE(description, ?),
            updated_at = ?
        WHERE game_id = ?
        """,
        (
            product_year,
            product_year,
            release_date,
            release_date,
            product_year,
            product_year,
            product_year,
            product_year,
            platform_json,
            description,
            now,
            target.game_id,
        ),
    )


def replace_game_reviews(
    conn: sqlite3.Connection,
    target: TargetGame,
    slug: str,
    product: dict,
    reviews: list[dict],
    now: str,
    replace_kaggle: bool,
) -> int:
    if replace_kaggle:
        conn.execute(
            "DELETE FROM reviews WHERE game_id = ? AND data_source = 'metacritic_kaggle'",
            (target.game_id,),
        )
        conn.execute(
            "DELETE FROM external_baseline WHERE game_id = ? AND data_source = 'metacritic_kaggle'",
            (target.game_id,),
        )
    conn.execute(
        "DELETE FROM reviews WHERE game_id = ? AND data_source = 'metacritic_web'",
        (target.game_id,),
    )
    conn.execute(
        "DELETE FROM external_baseline WHERE game_id = ? AND data_source = 'metacritic_web'",
        (target.game_id,),
    )

    repair_game_metadata(conn, target, product, now)

    source_url = f"{BASE_URL}/game/{slug}/critic-reviews/"
    score_summary = product.get("criticScoreSummary") or {}
    conn.execute(
        """
        INSERT OR REPLACE INTO game_identity
        (identity_id, game_id, source_name, external_id, external_slug,
         external_title, external_url, match_confidence, match_method,
         needs_manual_review, created_at, updated_at)
        VALUES (?, ?, 'metacritic_web', NULL, ?, ?, ?, 0.98,
                'metacritic_title_year', 0, ?, ?)
        """,
        (
            _identity_id(target.game_id),
            target.game_id,
            slug,
            product.get("title"),
            source_url,
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO external_baseline
        (baseline_id, game_id, target_id, source_platform, external_score,
         external_user_score, review_count, user_review_count, source_url,
         collected_at, data_source, license_note)
        VALUES (?, ?, NULL, 'metacritic', ?, NULL, ?, NULL, ?, ?,
                'metacritic_web', 'Metacritic public web JSON snapshot')
        """,
        (
            _baseline_id(target.game_id),
            target.game_id,
            float(score_summary["score"]) if score_summary.get("score") is not None else None,
            int(score_summary["reviewCount"]) if score_summary.get("reviewCount") is not None else len(reviews),
            source_url,
            now,
        ),
    )

    written = 0
    for item in reviews:
        score = item.get("score")
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            continue
        publication = item.get("publicationName") or "Unknown Source"
        source_id = upsert_source(conn, publication, now)
        conn.execute(
            """
            INSERT OR REPLACE INTO reviews
            (review_id, target_id, game_id, source_id, reviewer_id, title,
             original_score, original_score_value, original_score_scale,
             normalized_score, score_type, review_url, review_date, platform,
             language, summary, positive_points, negative_points,
             has_review_code_disclosure, has_sponsorship_disclosure,
             data_source, provenance_url, license_note, created_at, updated_at)
            VALUES (?, NULL, ?, ?, NULL, NULL, ?, ?, 100.0, ?, 'numeric',
                    ?, ?, ?, 'en', ?, NULL, NULL, NULL, NULL,
                    'metacritic_web', ?, 'Metacritic public web JSON snapshot', ?, ?)
            """,
            (
                _review_id(target.game_id, item),
                target.game_id,
                source_id,
                str(score_value),
                score_value,
                score_value,
                item.get("url"),
                item.get("date"),
                item.get("platform") or product.get("platform"),
                _truncate(item.get("quote")),
                source_url,
                now,
                now,
            ),
        )
        written += 1
    return written


def write_product_metadata(
    conn: sqlite3.Connection,
    target: TargetGame,
    slug: str,
    product: dict,
    now: str,
) -> None:
    repair_game_metadata(conn, target, product, now)

    source_url = f"{BASE_URL}/game/{slug}/"
    score_summary = product.get("criticScoreSummary") or {}
    conn.execute(
        """
        INSERT OR REPLACE INTO game_identity
        (identity_id, game_id, source_name, external_id, external_slug,
         external_title, external_url, match_confidence, match_method,
         needs_manual_review, created_at, updated_at)
        VALUES (?, ?, 'metacritic_web', NULL, ?, ?, ?, 0.95,
                'metacritic_metadata_title', 0, ?, ?)
        """,
        (
            _identity_id(target.game_id),
            target.game_id,
            slug,
            product.get("title"),
            source_url,
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO external_baseline
        (baseline_id, game_id, target_id, source_platform, external_score,
         external_user_score, review_count, user_review_count, source_url,
         collected_at, data_source, license_note)
        VALUES (?, ?, NULL, 'metacritic', ?, NULL, ?, NULL, ?, ?,
                'metacritic_web', 'Metacritic public web JSON product snapshot')
        """,
        (
            _baseline_id(target.game_id),
            target.game_id,
            float(score_summary["score"]) if score_summary.get("score") is not None else None,
            int(score_summary["reviewCount"]) if score_summary.get("reviewCount") is not None else None,
            source_url,
            now,
        ),
    )


def run(args: argparse.Namespace) -> None:
    ensure_dirs()
    cache_dir = Path(args.cache_dir) if args.cache_dir else METACRITIC_WEB_DIR
    client = MetacriticWebClient(
        cache_dir=cache_dir,
        refresh_cache=args.refresh_cache,
        user_agent=args.user_agent,
        sleep_seconds=args.sleep,
        retries=args.retries,
        retry_backoff=args.retry_backoff,
    )

    db_path = Path(args.db_path) if args.db_path else DB_PATH
    conn = connect_db(db_path)
    now = _now()

    totals = {
        "targets": 0,
        "matched": 0,
        "skipped": 0,
        "games_written": 0,
        "reviews_written": 0,
    }

    try:
        targets = load_targets(conn, args)
        totals["targets"] = len(targets)
        print(f"[metacritic_web] Loaded {len(targets):,} target games")

        for index, target in enumerate(targets, start=1):
            score = f"{target.weighted_score:.1f}" if target.weighted_score is not None else "n/a"
            print(
                f"  [{index}/{len(targets)}] {target.title} "
                f"(year={target.release_year or 'n/a'}, sample={target.sample_count}, score={score})"
            )

            slug, product, reason = find_product_for_target(client, target, args.year_tolerance)
            if not slug or not product:
                totals["skipped"] += 1
                print(f"      skip: {reason or 'no product match'}")
                continue

            product_year = product.get("premiereYear") or _year_from_date(product.get("releaseDate"))
            if args.metadata_missing_years:
                if not product_year:
                    totals["skipped"] += 1
                    print(f"      skip: product has no release year, slug={slug}")
                    continue

                totals["matched"] += 1
                print(
                    f"      match: slug={slug}, product_year={product_year}, "
                    f"reason={reason}"
                )

                if args.list_only or not args.write:
                    continue

                write_product_metadata(conn, target, slug, product, now)
                totals["games_written"] += 1
                conn.commit()
                print("      wrote metacritic_web product metadata")
                continue

            summary = product.get("criticScoreSummary") or {}
            listed_count = int(summary.get("reviewCount") or 0)
            if listed_count < args.min_review_count:
                totals["skipped"] += 1
                print(f"      skip: listed reviews {listed_count} < {args.min_review_count}")
                continue

            reviews = client.fetch_reviews(slug, args.page_size, listed_count)
            numeric_reviews = [item for item in reviews if item.get("score") is not None]
            if len(numeric_reviews) <= target.metacritic_kaggle_count:
                totals["skipped"] += 1
                print(
                    f"      skip: numeric reviews {len(numeric_reviews)} <= "
                    f"existing kaggle {target.metacritic_kaggle_count}"
                )
                continue

            totals["matched"] += 1
            print(
                f"      match: slug={slug}, product_year={product_year}, "
                f"listed={listed_count}, fetched={len(numeric_reviews)}, reason={reason}"
            )

            if args.list_only or not args.write:
                continue

            written = replace_game_reviews(
                conn=conn,
                target=target,
                slug=slug,
                product=product,
                reviews=numeric_reviews,
                now=now,
                replace_kaggle=args.replace_kaggle,
            )
            totals["games_written"] += 1
            totals["reviews_written"] += written
            conn.commit()
            print(f"      wrote {written} metacritic_web reviews")

        if args.write:
            conn.commit()

        print("\n[metacritic_web] === Summary ===")
        for key, value in totals.items():
            print(f"  {key:16s}: {value:,}")
        print(f"  cache_dir       : {cache_dir}")
        print(f"  db_path         : {db_path}")
        print(f"  write_enabled   : {args.write}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair Metacritic reviews or metadata from public web JSON.")
    parser.add_argument("--write", action="store_true", help="Write to SQLite. Default is dry-run.")
    parser.add_argument("--list-only", action="store_true", help="Resolve targets and fetch reviews, but do not write.")
    parser.add_argument(
        "--metadata-missing-years",
        action="store_true",
        help="Fill missing game release years from Metacritic product metadata instead of importing reviews.",
    )
    parser.add_argument(
        "--metadata-min-score",
        type=float,
        default=85.0,
        help="Minimum IMS weighted score for --metadata-missing-years targets.",
    )
    parser.add_argument(
        "--metadata-min-sample-count",
        type=int,
        default=75,
        help="Minimum review sample count for --metadata-missing-years targets.",
    )
    parser.add_argument(
        "--metadata-require-opencritic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require at least one OpenCritic review for --metadata-missing-years targets.",
    )
    parser.add_argument(
        "--metadata-skip-existing-identity",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip games that already have a metacritic_web identity row in metadata mode.",
    )
    parser.add_argument("--target-sample-counts", nargs="*", type=int, default=[50])
    parser.add_argument("--only-no-opencritic", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-existing-web", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--replace-kaggle", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-review-count", type=int, default=51)
    parser.add_argument("--year-tolerance", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--targets-csv", default=None, help="Optional CSV with game_id/title and metacritic_slug.")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--retry-backoff", type=float, default=1.0)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    try:
        run(args)
    except Exception as exc:
        print(f"[metacritic_web] ERROR: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
