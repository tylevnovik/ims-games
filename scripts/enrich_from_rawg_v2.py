"""Enrich IMS Games database with RAWG data -- v2 with improved matching.

Targets the 1,441 games still unmatched after v1 enrichment (platforms IS NULL).

Matching strategies (applied in order, most reliable first):
  1. Slug match (game_identity.external_slug == RAWG slug)
  2. Metacritic URL slug match
  3. Normalized title + release year
  4. Normalized title only  (with '&' -> 'and' normalization)
  5. Stripped title + year  (parens/editions removed, '&' -> 'and')
  6. Stripped title only
  7. Numeral variant + year (Roman <-> Arabic cross-matching)
  8. Numeral variant only
  9. Article-stripped + variant titles ("The X" -> "X", with numerals)
 10. Fuzzy token-set matching (Jaccard >= 0.7) -- second pass

Updates games table: developer, publisher, genres, platforms, description.
Backfills review platforms using pipe-separated ALL platforms.
"""

import json
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

# Add scripts/ to path so we can import config
sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH

RAWG_PATH = Path(__file__).parent.parent / "data" / "rawg" / "rawg_data.jsonl"


# ============================================================================
# Text normalization utilities
# ============================================================================

def norm_title(title: str) -> str:
    """Base normalization: lowercase, strip accents, '&' -> 'and', strip punct."""
    if not title:
        return ""
    t = unicodedata.normalize("NFD", title)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.lower()
    # Normalize ampersand to 'and' BEFORE stripping punctuation
    t = re.sub(r"&", " and ", t)
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def strip_parens(title: str) -> str:
    """Remove all parenthetical groups from a title."""
    return re.sub(r"\([^)]*\)", "", title).strip()


def strip_year_suffix(title: str) -> str:
    """Remove standalone 4-digit years (1980-2029) from a title."""
    t = re.sub(r"\b(19|20)\d{2}\b", "", title)
    return re.sub(r"\s+", " ", t).strip()


_EDITION_PAT = re.compile(
    r"\b("
    r"complete\s+edition|definitive\s+edition|deluxe\s+edition|"
    r"game\s+of\s+the\s+year|goty\s+edition|goty|"
    r"hd\s+remaster|hd\s+remastered|"
    r"remastered|remake|remaster|"
    r"enhanced\s+edition|special\s+edition|ultimate\s+edition|"
    r"gold\s+edition|collectors?\s+edition|"
    r"directors?\s+cut|anniversary\s+edition|"
    r"standard\s+edition|digital\s+edition"
    r")\b",
    re.IGNORECASE,
)


def strip_editions(title: str) -> str:
    """Remove edition suffixes from a title."""
    t = _EDITION_PAT.sub("", title)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def full_strip(title: str) -> str:
    """Apply all cleaning: parens, editions, year suffix.
    ('&' -> 'and' is handled by norm_title.)"""
    t = strip_parens(title)
    t = strip_editions(t)
    t = strip_year_suffix(t)
    return t


def extract_mc_slug(metacritic_url: str) -> str:
    """Extract game slug from a Metacritic URL."""
    if not metacritic_url:
        return ""
    m = re.search(r"/game/[^/]+/([^/?#]+)", metacritic_url)
    return m.group(1) if m else ""


# ============================================================================
# RAWG field extractors
# ============================================================================

def _extract_names(items):
    if not items:
        return None
    names = []
    for item in items:
        if isinstance(item, dict):
            if "name" in item:
                names.append(item["name"])
            elif "platform" in item:
                p = item["platform"]
                if isinstance(p, dict) and "name" in p:
                    names.append(p["name"])
    return ", ".join(names) if names else None


def _extract_platform_names(items):
    if not items:
        return []
    names = []
    for item in items:
        if isinstance(item, dict) and "platform" in item:
            p = item["platform"]
            if isinstance(p, dict) and "name" in p:
                names.append(p["name"])
    return names


def _extract_genre_names(items):
    if not items:
        return []
    return [x["name"] for x in items if isinstance(x, dict) and "name" in x]


# ============================================================================
# Numeral variant generation
# ============================================================================

_ROMAN_MAP = [
    (10, "x"), (9, "ix"), (8, "viii"), (7, "vii"), (6, "vi"),
    (5, "v"), (4, "iv"), (3, "iii"), (2, "ii"),
]


def numeral_variants(title: str) -> list[str]:
    """Generate title variants swapping Roman <-> Arabic numerals.

    Returns a (possibly empty) list of alternative forms.
    """
    variants = []
    # Roman -> Arabic  (e.g. "civilization iii" -> "civilization 3")
    for num, roman in _ROMAN_MAP:
        pat = re.compile(r"\b" + roman + r"\b")
        if pat.search(title):
            variants.append(pat.sub(str(num), title))
    # Arabic -> Roman  (e.g. "forza 4" -> "forza iv")
    for num, roman in _ROMAN_MAP:
        pat = re.compile(r"\b" + str(num) + r"\b")
        if pat.search(title):
            variants.append(pat.sub(roman, title))
    return variants


# ============================================================================
# Main enrichment
# ============================================================================

def enrich():
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        sys.exit(1)
    if not RAWG_PATH.exists():
        print(f"[ERROR] RAWG data not found: {RAWG_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # ==================================================================
    # Step 1: Load unmatched IMS games
    # ==================================================================
    print("Loading unmatched games (platforms IS NULL)...")
    unmatched = {}
    for row in conn.execute(
        "SELECT g.game_id, g.title, g.release_year "
        "FROM games g WHERE g.platforms IS NULL"
    ):
        unmatched[row["game_id"]] = {
            "title": row["title"],
            "year": row["release_year"],
        }
    print(f"  {len(unmatched):,} games to match")

    # ==================================================================
    # Step 2: Build pre-computed indices from IMS unmatched games
    # ==================================================================
    print("Building IMS indices...")

    # --- Slug & MC-slug indices (from game_identity) ---
    slug_idx = {}          # slug -> gid
    mc_slug_idx = {}       # mc_slug -> gid

    slug_rows = {}
    for row in conn.execute(
        "SELECT game_id, external_slug FROM game_identity "
        "WHERE external_slug IS NOT NULL AND game_id IN ("
        "  SELECT game_id FROM games WHERE platforms IS NULL)"
    ):
        gid = row["game_id"]
        slug = row["external_slug"].strip().lower()
        if slug:
            slug_rows.setdefault(gid, []).append(slug)

    # Populate slug_idx: slug -> gid  (for unmatched games only)
    for gid, slugs in slug_rows.items():
        for slug in slugs:
            slug_idx[slug] = gid

    # For MC slug matching: slugs containing dashes are likely MC slugs
    for gid, slugs in slug_rows.items():
        for slug in slugs:
            if "-" in slug:
                mc_slug_idx[gid] = slug  # gid -> expected mc slug

    print(f"  Slug index: {len(slug_idx):,} entries")
    print(f"  MC-slug candidates: {len(mc_slug_idx):,} games")

    # --- Title indices (multiple normalization levels) ---
    # All titles use norm_title() which now includes '&' -> 'and'
    ty_idx = {}            # (norm_title, year)  -> gid    [original titles]
    t_idx = {}             # norm_title           -> gid    [original titles]
    sty_idx = {}           # (stripped, year)     -> gid    [stripped titles]
    st_idx = {}            # stripped             -> gid    [stripped titles]

    # For fuzzy matching (pass 2)
    fuzzy_idx = {}         # stripped_norm -> gid
    fuzzy_gid_key = {}     # gid -> stripped_norm  (reverse lookup)

    # For article stripping (strategy 9): maps article-stripped key -> gid
    article_idx = {}       # norm_title_without_article -> gid

    for gid, info in unmatched.items():
        title = info["title"]
        year = info["year"]

        # Try to extract year from parenthetical in title: "God of War (2005)"
        paren_year = None
        m = re.search(r"\((\d{4})\)", title)
        if m:
            paren_year = int(m.group(1))
        effective_year = year or paren_year

        nt = norm_title(title)

        # Strip parens, editions, year suffixes
        stripped = full_strip(title)
        nst = norm_title(stripped)

        # Strategy 3/4: original normalized title
        if nt:
            if effective_year:
                ty_idx[(nt, effective_year)] = gid
            t_idx[nt] = gid

        # Strategy 5/6: stripped normalized title
        if nst and nst != nt:
            if effective_year:
                sty_idx[(nst, effective_year)] = gid
            st_idx[nst] = gid

        # Strategy 7/8: numeral variants of stripped title
        for v in numeral_variants(nst):
            nv = norm_title(v)
            if effective_year:
                sty_idx[(nv, effective_year)] = gid
            st_idx[nv] = gid

        # Strategy 9: article-stripped variants
        for article in ("the ", "a ", "an "):
            if nst.startswith(article):
                art_stripped = nst[len(article):]
                if art_stripped:
                    article_idx[art_stripped] = gid
                    st_idx[art_stripped] = gid
                    # Also add numeral variants of article-stripped
                    for v in numeral_variants(art_stripped):
                        nv = norm_title(v)
                        if nv:
                            article_idx[nv] = gid
                            st_idx[nv] = gid
            # Also try adding article (in case RAWG has "The X" but IMS has "X")
            with_art = article + nst
            # This direction: IMS "X" -> try matching RAWG "the x"
            # We store "the x" -> gid so when RAWG has "the x" it matches
            article_idx[with_art] = gid

        # Fuzzy index: stripped normalized title
        if nst:
            fuzzy_idx[nst] = gid
            fuzzy_gid_key[gid] = nst

    print(f"  Title+year index: {len(ty_idx):,}")
    print(f"  Title-only index: {len(t_idx):,}")
    print(f"  Stripped+year index: {len(sty_idx):,}")
    print(f"  Stripped-only index: {len(st_idx):,}")
    print(f"  Article index: {len(article_idx):,}")
    print(f"  Fuzzy index: {len(fuzzy_idx):,}")

    # ==================================================================
    # Step 3: Scan RAWG -- exact matching (strategies 1-9)
    # ==================================================================
    results = {}           # gid -> {developer, publisher, ...}
    stats = {
        "slug": 0, "mc_url": 0, "title_year": 0, "title": 0,
        "stripped_ty": 0, "stripped": 0,
        "numeral_ty": 0, "numeral": 0,
        "article": 0, "fuzzy": 0,
    }
    matched_gids = set()

    print(f"\nPass 1: Scanning RAWG ({RAWG_PATH})...")
    t0 = time.time()
    scanned = 0

    with open(RAWG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            scanned += 1
            if scanned % 100000 == 0:
                elapsed = time.time() - t0
                print(
                    f"  {scanned:,} records | "
                    f"{len(matched_gids):,} matched | "
                    f"{elapsed:.0f}s"
                )

            d = json.loads(line)
            rawg_slug = d.get("slug", "")
            rawg_name = d.get("name", "")
            rawg_year = None
            released = d.get("released")
            if released:
                try:
                    rawg_year = int(released[:4])
                except (ValueError, TypeError):
                    pass

            rawg_nt = norm_title(rawg_name)
            rawg_st = full_strip(rawg_name)
            rawg_nst = norm_title(rawg_st)

            gid = None
            method = None

            # --- Strategy 1: Direct slug match ---
            if rawg_slug and rawg_slug in slug_idx:
                gid = slug_idx[rawg_slug]
                method = "slug"

            # --- Strategy 2: Metacritic URL slug ---
            if not gid:
                mc_url = d.get("metacritic_url", "")
                mc_slug = extract_mc_slug(mc_url)
                if mc_slug and mc_slug in slug_idx:
                    gid = slug_idx[mc_slug]
                    method = "mc_url"

            # --- Strategy 3: Normalized title + year ---
            if not gid and rawg_nt and rawg_year:
                key = (rawg_nt, rawg_year)
                if key in ty_idx:
                    gid = ty_idx[key]
                    method = "title_year"

            # --- Strategy 4: Normalized title only ---
            if not gid and rawg_nt and rawg_nt in t_idx:
                gid = t_idx[rawg_nt]
                method = "title"

            # --- Strategy 5: Stripped title + year ---
            if not gid and rawg_nst and rawg_year:
                key = (rawg_nst, rawg_year)
                if key in sty_idx:
                    gid = sty_idx[key]
                    method = "stripped_ty"

            # --- Strategy 6: Stripped title only ---
            if not gid and rawg_nst and rawg_nst in st_idx:
                gid = st_idx[rawg_nst]
                method = "stripped"

            # --- Strategy 7 & 8: Numeral variants of RAWG name ---
            if not gid and rawg_nst:
                for v in numeral_variants(rawg_nst):
                    nv = norm_title(v)
                    if rawg_year:
                        key = (nv, rawg_year)
                        if key in sty_idx:
                            gid = sty_idx[key]
                            method = "numeral_ty"
                            break
                    if nv in st_idx:
                        gid = st_idx[nv]
                        method = "numeral"
                        break

            # --- Strategy 9: Article-stripped RAWG name ---
            if not gid and rawg_nst:
                for article in ("the ", "a ", "an "):
                    if rawg_nst.startswith(article):
                        art_stripped = rawg_nst[len(article):]
                        if art_stripped in article_idx:
                            gid = article_idx[art_stripped]
                            method = "article"
                            break
                        if art_stripped in st_idx:
                            gid = st_idx[art_stripped]
                            method = "article"
                            break

            # Skip if no match or already matched
            if not gid or gid in matched_gids:
                continue

            # Record the match
            matched_gids.add(gid)
            stats[method] += 1

            developer = _extract_names(d.get("developers"))
            publisher = _extract_names(d.get("publishers"))
            genres = _extract_genre_names(d.get("genres"))
            platforms = _extract_platform_names(d.get("parent_platforms"))
            description = d.get("description_raw") or None

            results[gid] = {
                "developer": developer,
                "publisher": publisher,
                "genres": genres,
                "platforms": platforms,
                "description": description,
            }

    elapsed = time.time() - t0
    print(f"\n  Scan complete: {scanned:,} records in {elapsed:.1f}s")

    # --- Exact match stats ---
    print("\n--- Exact match results ---")
    total_exact = 0
    for method, count in stats.items():
        if method != "fuzzy" and count:
            print(f"  {method:15s}: {count:,}")
            total_exact += count
    print(f"  {'total exact':15s}: {total_exact:,}")

    remaining = len(unmatched) - len(matched_gids)
    print(f"  Remaining unmatched: {remaining:,}")

    # ==================================================================
    # Step 4: Pass 2 -- Fuzzy token-set matching (Jaccard >= 0.7)
    # ==================================================================
    still_unmatched_gids = [
        gid for gid in unmatched if gid not in matched_gids
    ]

    if still_unmatched_gids:
        print(f"\nPass 2: Fuzzy matching {len(still_unmatched_gids):,} remaining games...")

        # Build inverted token index from remaining unmatched IMS games
        inv_idx = {}   # token -> set of gids
        remaining_fuzzy = {}  # gid -> token_set

        for gid in still_unmatched_gids:
            nst = fuzzy_gid_key.get(gid, "")
            if not nst:
                continue
            tokens = frozenset(nst.split())
            if not tokens:
                continue
            remaining_fuzzy[gid] = tokens
            for tok in tokens:
                if tok not in inv_idx:
                    inv_idx[tok] = set()
                inv_idx[tok].add(gid)

        # Filter out very high-frequency tokens for candidate generation
        high_freq = {
            tok for tok, gids in inv_idx.items() if len(gids) > 200
        }
        if high_freq:
            print(f"  Filtering {len(high_freq)} high-frequency tokens "
                  f"(appear in >200 games)")

        print(f"  Inverted index: {len(inv_idx):,} unique tokens")
        print("  Re-scanning RAWG for fuzzy matches...")
        t1 = time.time()
        fuzzy_count = 0
        scanned2 = 0

        with open(RAWG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                scanned2 += 1
                if scanned2 % 100000 == 0:
                    print(
                        f"  {scanned2:,} | "
                        f"{fuzzy_count} fuzzy matches | "
                        f"{time.time() - t1:.0f}s"
                    )

                if not remaining_fuzzy:
                    break

                d = json.loads(line)
                rawg_name = d.get("name", "")
                rawg_st = full_strip(rawg_name)
                rawg_nst = norm_title(rawg_st)
                if not rawg_nst:
                    continue

                rawg_tokens = set(rawg_nst.split())
                if not rawg_tokens:
                    continue

                # Find candidate IMS games sharing at least one non-freq token
                candidates = {}
                for tok in rawg_tokens:
                    if tok in high_freq:
                        continue
                    if tok in inv_idx:
                        for gid in inv_idx[tok]:
                            if gid not in matched_gids:
                                candidates[gid] = True

                if not candidates:
                    continue

                # Evaluate Jaccard similarity for each candidate
                best_score = 0.0
                best_gid = None

                for c_gid in candidates:
                    if c_gid not in remaining_fuzzy:
                        continue
                    ims_tokens = remaining_fuzzy[c_gid]
                    if not ims_tokens:
                        continue

                    # Quick size filter for Jaccard >= 0.7
                    lt = len(ims_tokens)
                    rt = len(rawg_tokens)
                    if min(lt, rt) / max(lt, rt) < 0.7:
                        continue

                    intersection = len(ims_tokens & rawg_tokens)
                    union = len(ims_tokens | rawg_tokens)
                    if union == 0:
                        continue
                    jaccard = intersection / union

                    if jaccard >= 0.7 and jaccard > best_score:
                        best_score = jaccard
                        best_gid = c_gid

                if best_gid:
                    matched_gids.add(best_gid)
                    stats["fuzzy"] += 1
                    fuzzy_count += 1

                    developer = _extract_names(d.get("developers"))
                    publisher = _extract_names(d.get("publishers"))
                    genres = _extract_genre_names(d.get("genres"))
                    platforms = _extract_platform_names(
                        d.get("parent_platforms")
                    )
                    description = d.get("description_raw") or None

                    results[best_gid] = {
                        "developer": developer,
                        "publisher": publisher,
                        "genres": genres,
                        "platforms": platforms,
                        "description": description,
                    }

                    # Remove from fuzzy candidate pool
                    del remaining_fuzzy[best_gid]

        elapsed_fuzzy = time.time() - t1
        print(f"  Fuzzy scan complete: {scanned2:,} records in "
              f"{elapsed_fuzzy:.1f}s")
        print(f"  Fuzzy matches found: {fuzzy_count}")

    remaining_final = len(unmatched) - len(matched_gids)
    print(f"\n  Remaining unmatched after all strategies: {remaining_final:,}")

    # ==================================================================
    # Step 5: Apply game metadata updates
    # ==================================================================
    if results:
        print(f"\nUpdating {len(results):,} games...")
        update_rows = []
        for gid, data in results.items():
            genres_str = (
                json.dumps(data["genres"], ensure_ascii=False)
                if data["genres"]
                else None
            )
            platforms_str = (
                json.dumps(data["platforms"], ensure_ascii=False)
                if data["platforms"]
                else None
            )
            update_rows.append((
                data["developer"],
                data["publisher"],
                genres_str,
                platforms_str,
                data["description"],
                gid,
            ))

        conn.executemany(
            """UPDATE games SET
                developer = ?, publisher = ?, genres = ?,
                platforms = ?, description = ?
            WHERE game_id = ?""",
            update_rows,
        )
        conn.commit()
        print(f"  Updated {len(update_rows):,} games.")
    else:
        print("\nNo new matches found.")

    # ==================================================================
    # Step 6: Backfill review platforms (pipe-separated ALL platforms)
    # ==================================================================
    print("\nBackfilling review platforms...")
    game_plat_map = {}
    for row in conn.execute(
        "SELECT game_id, platforms FROM games WHERE platforms IS NOT NULL"
    ):
        try:
            plats = json.loads(row[1])
            if plats and isinstance(plats, list):
                # Pipe-separated ALL platforms
                game_plat_map[row[0]] = "|".join(
                    p for p in plats if isinstance(p, str)
                )
        except (json.JSONDecodeError, TypeError):
            pass
    print(f"  Games with platform data: {len(game_plat_map):,}")

    conn.execute("DROP TABLE IF EXISTS _platform_map")
    conn.execute(
        "CREATE TEMP TABLE _platform_map "
        "(game_id TEXT PRIMARY KEY, platform TEXT)"
    )
    conn.executemany(
        "INSERT INTO _platform_map (game_id, platform) VALUES (?, ?)",
        list(game_plat_map.items()),
    )
    conn.commit()

    cursor = conn.execute("""
        UPDATE reviews
        SET platform = (
            SELECT pm.platform
            FROM _platform_map pm
            WHERE pm.game_id = reviews.game_id
        )
        WHERE reviews.platform IS NULL
          AND reviews.game_id IN (SELECT game_id FROM _platform_map)
    """)
    conn.commit()
    updated_reviews = cursor.rowcount
    print(f"  Updated {updated_reviews:,} reviews with platform data")

    conn.execute("DROP TABLE IF EXISTS _platform_map")
    conn.commit()

    # ==================================================================
    # Step 7: Final verification
    # ==================================================================
    print("\n=== Final verification ===")
    total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    for col in ["developer", "publisher", "genres", "platforms", "description"]:
        filled = conn.execute(
            f"SELECT COUNT(*) FROM games "
            f"WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchone()[0]
        pct = 100 * filled / total if total else 0
        print(f"  {col:15s}: {filled:,}/{total:,} ({pct:.1f}%)")

    # Review platform coverage
    rev_filled = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE platform IS NOT NULL"
    ).fetchone()[0]
    rev_total = conn.execute(
        "SELECT COUNT(*) FROM reviews"
    ).fetchone()[0]
    if rev_total:
        pct = 100 * rev_filled / rev_total
    else:
        pct = 0
    print(f"  {'reviews.plat':15s}: {rev_filled:,}/{rev_total:,} ({pct:.1f}%)")

    # Show some still-unmatched titles for reference
    still_unmatched_titles = sorted(
        unmatched[gid]["title"]
        for gid in unmatched
        if gid not in matched_gids
    )
    if still_unmatched_titles:
        print(f"\n=== Still unmatched ({len(still_unmatched_titles):,} games) ===")
        for title in still_unmatched_titles[:30]:
            print(f"  {title}")
        if len(still_unmatched_titles) > 30:
            print(f"  ... and {len(still_unmatched_titles) - 30} more")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    enrich()
