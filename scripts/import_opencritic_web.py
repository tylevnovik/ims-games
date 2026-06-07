"""Import OpenCritic public web snapshots into the IMS Games database.

This is a pragmatic backfill path for recent years when a licensed API export is
not available. It reads OpenCritic's server-rendered JSON state from public pages
and stores only structured review fields, short snippets, and source links.

Usage:
    python import_opencritic_web.py --years 2024 2025 2026          # dry run
    python import_opencritic_web.py --years 2024 2025 2026 --write  # write DB
    python import_opencritic_web.py --years 2011 2012 2013 \
        --write --only-existing-low-sample                         # legacy cap repair
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sqlite3
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import DB_PATH, OPENCRITIC_DIR, ensure_dirs
from source_identity import canonical_source_name, source_id_for_name

BASE_URL = "https://opencritic.com"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; IMS-Games-Backfill/0.1)"

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


def game_id_for(title: str) -> str:
    """Use the same exact-title id scheme as the Metacritic importer."""
    return f"mc-{_md5(title)[:16]}"


def review_id_for(review: dict, game_id: str) -> str:
    raw_id = review.get("_id")
    if raw_id:
        return f"oc-rev-{raw_id}"
    outlet = (review.get("Outlet") or {}).get("name") or ""
    url = review.get("externalUrl") or ""
    date = review.get("publishedDate") or ""
    score = review.get("score") if review.get("score") is not None else review.get("npScore")
    return f"oc-rev-{_md5(f'{game_id}|{outlet}|{url}|{date}|{score}')[:20]}"


def identity_id_for(opencritic_id: int | str) -> str:
    return f"oc-id-{opencritic_id}"


def baseline_id_for(opencritic_id: int | str) -> str:
    return f"oc-bl-{opencritic_id}"


def _year_from_date(date_value: object) -> int | None:
    if not date_value:
        return None
    match = re.match(r"(\d{4})", str(date_value))
    return int(match.group(1)) if match else None


def _json_list(items: list[str]) -> str | None:
    cleaned = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def _normalize_game_title(title: str) -> str:
    text = str(title or "")
    text = re.sub(r"\s*\(((?:19|20)\d{2})\)\s*$", "", text)
    ascii_title = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    lowered = ascii_title.lower()
    alnum = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", alnum).strip()


def _game_slug(game: dict) -> str:
    url = game.get("url") or ""
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "game":
        return parts[2]
    title = re.sub(r"[^a-z0-9]+", "-", str(game.get("name") or "").lower()).strip("-")
    return title or str(game.get("id"))


def _absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return BASE_URL + url
    return f"{BASE_URL}/{url}"


class OpenCriticWebClient:
    def __init__(
        self,
        cache_dir: Path,
        refresh_cache: bool,
        user_agent: str,
        sleep_seconds: float,
        retries: int,
        retry_backoff: float,
    ):
        self.cache_dir = cache_dir
        self.refresh_cache = refresh_cache
        self.user_agent = user_agent
        self.sleep_seconds = sleep_seconds
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, url: str) -> str:
        cache_path = self.cache_dir / f"{_md5(url)}.html"
        if cache_path.exists() and not self.refresh_cache:
            return cache_path.read_text(encoding="utf-8")

        req = Request(url, headers={"User-Agent": self.user_agent})
        max_attempts = max(1, self.retries + 1)
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                with urlopen(req, timeout=40) as response:
                    text = response.read().decode("utf-8", "replace")
                break
            except HTTPError as exc:
                if exc.code < 500 and exc.code not in (408, 429):
                    raise RuntimeError(f"Could not fetch {url}: {exc}") from exc
                last_exc = exc
            except (URLError, TimeoutError, HTTPException, ConnectionError, OSError) as exc:
                last_exc = exc

            if attempt >= max_attempts:
                raise RuntimeError(f"Could not fetch {url}: {last_exc}") from last_exc

            wait = self.retry_backoff * (2 ** (attempt - 1))
            print(
                f"[opencritic_web] retry {attempt}/{max_attempts - 1} after fetch failure: {url} ({last_exc})",
                flush=True,
            )
            if wait > 0:
                time.sleep(wait)

        cache_path.write_text(text, encoding="utf-8")
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return text

    @staticmethod
    def parse_state(page_html: str) -> dict:
        match = re.search(
            r'<script id="serverApp-state" type="application/json">(.*?)</script>',
            page_html,
            flags=re.S,
        )
        if not match:
            raise ValueError("serverApp-state JSON not found")

        raw = html.unescape(match.group(1))
        raw = (
            raw.replace("&q;", '"')
            .replace("&a;", "&")
            .replace("&s;", "'")
            .replace("&l;", "<")
            .replace("&g;", ">")
        )
        return json.loads(raw)


def _extract_year_games(state: dict, year: int) -> list[dict]:
    for key, value in state.items():
        if key.startswith("api/game") and f"time={year}" in key and isinstance(value, list):
            return value
    for key, value in state.items():
        if key.startswith("api/game") and isinstance(value, list):
            return value
    return []


def fetch_games_for_year(
    client: OpenCriticWebClient,
    year: int,
    max_pages: int,
    max_games: int | None,
) -> list[dict]:
    games: list[dict] = []
    seen_ids: set[int] = set()

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/browse/all/{year}"
        if page > 1:
            url += f"?page={page}"
        state = client.parse_state(client.fetch(url))
        page_games = _extract_year_games(state, year)
        new_games = []

        for game in page_games:
            oc_id = game.get("id")
            if oc_id is None or oc_id in seen_ids:
                continue
            seen_ids.add(oc_id)
            new_games.append(game)
            games.append(game)
            if max_games and len(games) >= max_games:
                return games

        print(f"[opencritic_web] {year} page {page}: {len(new_games)} new games")
        if not page_games or not new_games:
            break

    return games


def _extract_reviews(state: dict, opencritic_id: int | str) -> list[dict]:
    prefix = f"game/game/{opencritic_id}/"
    for key, value in state.items():
        if key.startswith(prefix) and isinstance(value, list):
            return value
    return []


def _extract_game_detail(state: dict, opencritic_id: int | str) -> dict:
    detail = state.get(f"game/{opencritic_id}")
    return detail if isinstance(detail, dict) else {}


def fetch_reviews_for_game(
    client: OpenCriticWebClient,
    game: dict,
    max_review_pages: int | None,
) -> tuple[dict, list[dict]]:
    oc_id = game["id"]
    slug = _game_slug(game)
    expected = int(game.get("numReviews") or 0)
    page_cap = max_review_pages or max(1, math.ceil(expected / 20) + 1)

    all_reviews: list[dict] = []
    seen_review_ids: set[str] = set()
    detail: dict = {}

    for page in range(1, page_cap + 1):
        url = f"{BASE_URL}/game/{oc_id}/{slug}/reviews"
        if page > 1:
            url += f"?page={page}"
        state = client.parse_state(client.fetch(url))
        detail = detail or _extract_game_detail(state, oc_id)
        page_reviews = _extract_reviews(state, oc_id)

        new_count = 0
        for review in page_reviews:
            rid = review_id_for(review, str(oc_id))
            if rid in seen_review_ids:
                continue
            seen_review_ids.add(rid)
            all_reviews.append(review)
            new_count += 1

        if not page_reviews or new_count == 0:
            break

    return detail, all_reviews


def _platform_names(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    names = []
    for item in raw:
        if isinstance(item, dict):
            names.append(item.get("shortName") or item.get("name") or "")
        else:
            names.append(str(item))
    return [str(name).strip() for name in names if str(name).strip()]


def _genre_names(game: dict) -> list[str]:
    raw_genres = game.get("Genres") or game.get("tags") or []
    names = []
    if isinstance(raw_genres, list):
        for item in raw_genres:
            if isinstance(item, dict):
                names.append(item.get("name") or "")
            else:
                names.append(str(item))
    return [str(name).strip() for name in names if str(name).strip()]


def _review_platform(review: dict) -> str | None:
    names = _platform_names(review.get("Platforms"))
    return names[0] if names else None


def _review_score(review: dict) -> float | None:
    score = review.get("score")
    if score is None:
        score = review.get("npScore")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def connect_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}. Run init_db.py first.")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def load_existing_game_lookup(conn: sqlite3.Connection) -> dict:
    by_title_year = {}
    by_title: dict[str, list[str]] = {}
    for row in conn.execute("SELECT game_id, title, release_year FROM games"):
        norm = _normalize_game_title(row["title"])
        if not norm:
            continue
        if row["release_year"] is not None:
            by_title_year[(norm, int(row["release_year"]))] = row["game_id"]
        by_title.setdefault(norm, []).append(row["game_id"])
    return {"by_title_year": by_title_year, "by_title": by_title}


def load_non_opencritic_review_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT game_id, COUNT(*) AS c
        FROM reviews
        WHERE data_source <> 'opencritic_web'
        GROUP BY game_id
        """
    ).fetchall()
    return {row["game_id"]: int(row["c"] or 0) for row in rows}


def resolve_game_id(title: str, release_year: int | None, lookup: dict) -> str:
    norm = _normalize_game_title(title)
    if release_year is not None:
        existing = lookup["by_title_year"].get((norm, release_year))
        if existing:
            return existing
    title_matches = lookup["by_title"].get(norm, [])
    if len(set(title_matches)) == 1:
        return title_matches[0]
    return game_id_for(title)


def resolved_existing_game_id(game: dict, fallback_year: int, lookup: dict, existing_counts: dict[str, int]) -> str | None:
    title = str(game.get("name") or "").strip()
    if not title:
        return None
    release_year = _year_from_date(game.get("firstReleaseDate")) or fallback_year
    game_id = resolve_game_id(title, release_year, lookup)
    return game_id if game_id in existing_counts else None


def filter_existing_low_sample_games(
    games: list[dict],
    year: int,
    lookup: dict,
    existing_counts: dict[str, int],
    max_existing_reviews: int,
    min_opencritic_reviews: int,
) -> list[dict]:
    selected: list[dict] = []
    skipped_unmatched = 0
    skipped_enough_existing = 0
    skipped_low_opencritic = 0

    for game in games:
        game_id = resolved_existing_game_id(game, year, lookup, existing_counts)
        if game_id is None:
            skipped_unmatched += 1
            continue

        current_reviews = existing_counts.get(game_id, 0)
        oc_reviews = int(game.get("numReviews") or 0)
        if current_reviews > max_existing_reviews:
            skipped_enough_existing += 1
            continue
        if oc_reviews < min_opencritic_reviews or oc_reviews <= current_reviews:
            skipped_low_opencritic += 1
            continue

        game["_resolved_existing_game_id"] = game_id
        game["_existing_review_count"] = current_reviews
        selected.append(game)

    print(
        "[opencritic_web] Targeted filter: "
        f"selected={len(selected)}, unmatched={skipped_unmatched}, "
        f"existing_above_cap={skipped_enough_existing}, low_oc_gain={skipped_low_opencritic}"
    )
    return selected


def remember_game_id(title: str, release_year: int | None, game_id: str, lookup: dict) -> None:
    norm = _normalize_game_title(title)
    if not norm:
        return
    if release_year is not None:
        lookup["by_title_year"][(norm, release_year)] = game_id
    lookup["by_title"].setdefault(norm, [])
    if game_id not in lookup["by_title"][norm]:
        lookup["by_title"][norm].append(game_id)


def upsert_game(
    conn: sqlite3.Connection,
    game: dict,
    detail: dict,
    now: str,
    lookup: dict,
) -> str:
    title = str((detail.get("name") or game.get("name") or "")).strip()
    if not title:
        raise ValueError(f"OpenCritic game has no name: {game}")

    release_date = detail.get("firstReleaseDate") or game.get("firstReleaseDate")
    release_year = _year_from_date(release_date)
    game_id = resolve_game_id(title, release_year, lookup)
    platforms = _json_list(_platform_names(detail.get("Platforms") or game.get("Platforms")))
    genres = _json_list(_genre_names(detail or game))
    description = _truncate(detail.get("description") or (detail.get("reviewSummary") or {}).get("summary"))

    conn.execute(
        """
        INSERT INTO games
        (game_id, title, title_original, release_date, release_year, developer,
         publisher, genres, platforms, description, created_at, updated_at)
        VALUES (?, ?, NULL, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET
            release_date = CASE
                WHEN excluded.release_year IS NOT NULL
                 AND (games.release_year IS NULL OR excluded.release_year < games.release_year)
                THEN excluded.release_date
                ELSE COALESCE(games.release_date, excluded.release_date)
            END,
            release_year = CASE
                WHEN excluded.release_year IS NOT NULL
                 AND (games.release_year IS NULL OR excluded.release_year < games.release_year)
                THEN excluded.release_year
                ELSE COALESCE(games.release_year, excluded.release_year)
            END,
            genres = COALESCE(games.genres, excluded.genres),
            platforms = COALESCE(games.platforms, excluded.platforms),
            description = COALESCE(games.description, excluded.description),
            updated_at = excluded.updated_at
        """,
        (game_id, title, release_date, release_year, genres, platforms, description, now, now),
    )
    remember_game_id(title, release_year, game_id, lookup)
    return game_id


def upsert_identity_and_baseline(
    conn: sqlite3.Connection,
    game_id: str,
    game: dict,
    detail: dict,
    now: str,
) -> None:
    oc_id = game["id"]
    title = detail.get("name") or game.get("name")
    source_url = _absolute_url(detail.get("url") or game.get("url") or f"/game/{oc_id}/{_game_slug(game)}")
    conn.execute(
        """
        INSERT OR REPLACE INTO game_identity
        (identity_id, game_id, source_name, external_id, external_slug,
         external_title, external_url, match_confidence, match_method,
         needs_manual_review, created_at, updated_at)
        VALUES (?, ?, 'opencritic_web', ?, ?, ?, ?, 0.95, 'opencritic_title_year', 0, ?, ?)
        """,
        (
            identity_id_for(oc_id),
            game_id,
            str(oc_id),
            _game_slug(game),
            title,
            source_url,
            now,
            now,
        ),
    )

    score = detail.get("topCriticScore", game.get("topCriticScore"))
    review_count = detail.get("numReviews", game.get("numReviews"))
    conn.execute(
        """
        INSERT OR REPLACE INTO external_baseline
        (baseline_id, game_id, target_id, source_platform, external_score,
         external_user_score, review_count, user_review_count, source_url,
         collected_at, data_source, license_note)
        VALUES (?, ?, NULL, 'opencritic', ?, NULL, ?, NULL, ?, ?, 'opencritic_web',
                'OpenCritic public web snapshot')
        """,
        (
            baseline_id_for(oc_id),
            game_id,
            float(score) if score is not None else None,
            int(review_count) if review_count is not None else None,
            source_url,
            now,
        ),
    )


def upsert_source(conn: sqlite3.Connection, outlet: dict, now: str) -> str:
    source_name = canonical_source_name(outlet.get("name") or "Unknown Source")
    source_id = source_id_for_name(source_name)
    website_url = None
    conn.execute(
        """
        INSERT INTO sources
        (source_id, name, source_type, country_region, language, website_url,
         is_institutional, is_individual_creator, inclusion_status, notes,
         created_at, updated_at)
        VALUES (?, ?, 'media', NULL, NULL, ?, 1, 0, 'active',
                'Imported or linked from OpenCritic public web snapshot', ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            name = COALESCE(sources.name, excluded.name),
            website_url = COALESCE(sources.website_url, excluded.website_url),
            updated_at = excluded.updated_at
        """,
        (source_id, source_name, website_url, now, now),
    )
    return source_id


def upsert_review(
    conn: sqlite3.Connection,
    game_id: str,
    review: dict,
    now: str,
) -> bool:
    outlet = review.get("Outlet") or {}
    source_id = upsert_source(conn, outlet, now)
    score = _review_score(review)
    if score is None:
        return False

    original_url = review.get("externalUrl")
    conn.execute(
        """
        INSERT OR REPLACE INTO reviews
        (review_id, target_id, game_id, source_id, reviewer_id, title,
         original_score, original_score_value, original_score_scale,
         normalized_score, score_type, review_url, review_date, platform,
         language, summary, positive_points, negative_points,
         has_review_code_disclosure, has_sponsorship_disclosure,
         data_source, provenance_url, license_note, created_at, updated_at)
        VALUES (?, NULL, ?, ?, NULL, ?, ?, ?, 100.0, ?, 'numeric', ?, ?, ?,
                ?, ?, NULL, NULL, NULL, NULL, 'opencritic_web', ?,
                'OpenCritic public web snapshot', ?, ?)
        """,
        (
            review_id_for(review, game_id),
            game_id,
            source_id,
            _truncate(review.get("title"), 500),
            str(score),
            score,
            score,
            original_url,
            review.get("publishedDate"),
            _review_platform(review),
            review.get("language"),
            _truncate(review.get("snippet")),
            original_url,
            now,
            now,
        ),
    )
    return True


def purge_existing_opencritic_web(conn: sqlite3.Connection) -> None:
    candidate_game_ids = [
        row["game_id"]
        for row in conn.execute(
            "SELECT DISTINCT game_id FROM game_identity WHERE source_name = 'opencritic_web'"
        )
    ]
    conn.execute("DELETE FROM reviews WHERE data_source = 'opencritic_web'")
    conn.execute("DELETE FROM external_baseline WHERE data_source = 'opencritic_web'")
    conn.execute("DELETE FROM game_identity WHERE source_name = 'opencritic_web'")
    for game_id in candidate_game_ids:
        conn.execute(
            """
            DELETE FROM games
            WHERE game_id = ?
              AND NOT EXISTS (SELECT 1 FROM reviews WHERE reviews.game_id = games.game_id)
              AND NOT EXISTS (SELECT 1 FROM game_identity WHERE game_identity.game_id = games.game_id)
              AND NOT EXISTS (SELECT 1 FROM external_baseline WHERE external_baseline.game_id = games.game_id)
            """,
            (game_id,),
        )


def write_game_payload(
    conn: sqlite3.Connection,
    game: dict,
    detail: dict,
    reviews: list[dict],
    now: str,
    game_lookup: dict,
) -> int:
    game_id = upsert_game(conn, game, detail, now, game_lookup)
    upsert_identity_and_baseline(conn, game_id, game, detail, now)
    written = 0
    for review in reviews:
        if upsert_review(conn, game_id, review, now):
            written += 1
    return written


def run(args: argparse.Namespace) -> None:
    ensure_dirs()
    cache_dir = Path(args.cache_dir) if args.cache_dir else OPENCRITIC_DIR / "web-cache"
    client = OpenCriticWebClient(
        cache_dir=cache_dir,
        refresh_cache=args.refresh_cache,
        user_agent=args.user_agent,
        sleep_seconds=args.sleep,
        retries=args.retries,
        retry_backoff=args.retry_backoff,
    )

    db_path = Path(args.db_path) if args.db_path else DB_PATH
    conn = connect_db(db_path) if (args.write or args.only_existing_low_sample) else None
    now = _now()

    totals = {
        "games_seen": 0,
        "games_written": 0,
        "reviews_seen": 0,
        "reviews_written": 0,
    }

    try:
        if args.write and conn and args.replace:
            print("[opencritic_web] Removing previous opencritic_web rows...")
            purge_existing_opencritic_web(conn)
        game_lookup = load_existing_game_lookup(conn) if conn else {"by_title_year": {}, "by_title": {}}
        existing_counts = load_non_opencritic_review_counts(conn) if conn and args.only_existing_low_sample else {}

        for year in args.years:
            print(f"\n[opencritic_web] Fetching year {year}...")
            games = fetch_games_for_year(client, year, args.max_pages, args.max_games)
            print(f"[opencritic_web] {year}: {len(games)} games discovered")
            if args.only_existing_low_sample:
                games = filter_existing_low_sample_games(
                    games=games,
                    year=year,
                    lookup=game_lookup,
                    existing_counts=existing_counts,
                    max_existing_reviews=args.max_existing_reviews,
                    min_opencritic_reviews=args.min_opencritic_reviews,
                )
                print(f"[opencritic_web] {year}: {len(games)} targeted games after filtering")
            if args.list_only:
                totals["games_seen"] += len(games)
                for idx, game in enumerate(games[: args.list_preview], start=1):
                    title = game.get("name") or f"OpenCritic game {game.get('id')}"
                    existing = game.get("_existing_review_count")
                    existing_note = f", existing={existing}" if existing is not None else ""
                    print(
                        f"  [{idx}/{len(games)}] {title}"
                        f" (oc={game.get('numReviews') or 0}{existing_note})"
                    )
                if len(games) > args.list_preview:
                    print(f"  ... {len(games) - args.list_preview} more target games")
                continue

            def handle_game(idx: int, game: dict, detail: dict, reviews: list[dict]) -> None:
                title = game.get("name") or f"OpenCritic game {game.get('id')}"
                existing_note = ""
                if "_existing_review_count" in game:
                    existing_note = f" (existing={game['_existing_review_count']}, oc={game.get('numReviews') or 0})"
                print(f"  [{idx}/{len(games)}] {title}{existing_note}")
                totals["games_seen"] += 1
                totals["reviews_seen"] += len(reviews)

                if not args.write:
                    print(f"      dry-run: {len(reviews)} review rows")
                    return

                written = write_game_payload(conn, game, detail, reviews, now, game_lookup)
                totals["games_written"] += 1
                totals["reviews_written"] += written
                print(f"      wrote {written}/{len(reviews)} numeric reviews")

            if args.workers <= 1:
                for idx, game in enumerate(games, start=1):
                    detail, reviews = fetch_reviews_for_game(client, game, args.max_review_pages)
                    handle_game(idx, game, detail, reviews)
            else:
                print(f"[opencritic_web] Fetching review pages with {args.workers} workers")
                with ThreadPoolExecutor(max_workers=args.workers) as executor:
                    future_map = {
                        executor.submit(fetch_reviews_for_game, client, game, args.max_review_pages): game
                        for game in games
                    }
                    for idx, future in enumerate(as_completed(future_map), start=1):
                        game = future_map.pop(future)
                        detail, reviews = future.result()
                        handle_game(idx, game, detail, reviews)

            if args.write and conn:
                conn.commit()

        print("\n[opencritic_web] === Summary ===")
        for key, value in totals.items():
            print(f"  {key:16s}: {value:,}")
        print(f"  cache_dir       : {cache_dir}")
        print(f"  db_path         : {db_path}")
        print(f"  write_enabled   : {args.write}")

    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill OpenCritic public web snapshot data.")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    parser.add_argument("--write", action="store_true", help="Write to SQLite. Default is dry-run.")
    parser.add_argument("--replace", action="store_true", help="Delete previous opencritic_web rows first.")
    parser.add_argument("--max-pages", type=int, default=50, help="Max browse pages per year.")
    parser.add_argument("--max-games", type=int, default=None, help="Max games per year, useful for tests.")
    parser.add_argument("--max-review-pages", type=int, default=None, help="Max review pages per game.")
    parser.add_argument("--list-only", action="store_true", help="Only list discovered/targeted games; do not fetch review pages.")
    parser.add_argument("--list-preview", type=int, default=20, help="Rows to print per year with --list-only.")
    parser.add_argument(
        "--only-existing-low-sample",
        action="store_true",
        help="Only fetch OpenCritic reviews for games already in the DB with low non-OpenCritic sample counts.",
    )
    parser.add_argument(
        "--max-existing-reviews",
        type=int,
        default=65,
        help="Target existing games with at most this many non-OpenCritic reviews.",
    )
    parser.add_argument(
        "--min-opencritic-reviews",
        type=int,
        default=20,
        help="Target only OpenCritic games with at least this many listed reviews.",
    )
    parser.add_argument("--cache-dir", default=None, help="HTML cache directory.")
    parser.add_argument("--db-path", default=None, help="SQLite DB path. Defaults to data/db/ims_games.sqlite.")
    parser.add_argument("--refresh-cache", action="store_true", help="Ignore cached HTML and refetch.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay after live fetches.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent review-page fetch workers.")
    parser.add_argument("--retries", type=int, default=4, help="Live fetch retries per page.")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="Initial retry delay in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    try:
        run(args)
    except Exception as exc:
        print(f"[opencritic_web] ERROR: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
