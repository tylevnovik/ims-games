"""
Analyze unmatched IMS Games that failed to match against the RAWG dataset.
Unmatched games are identified by: games.platforms IS NULL
"""
import sqlite3
import re
import unicodedata
from collections import Counter, defaultdict

DB_PATH = r"C:\Users\blmpt\PycharmProjects\CWSS\data\db\ims_games.sqlite"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """Replicate the project's normalize_title function."""
    nfkd = unicodedata.normalize("NFD", title)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    low = stripped.lower()
    alnum = re.sub(r"[^a-z0-9\s]", "", low)
    return re.sub(r"\s+", " ", alnum).strip()


ROMAN_MAP = {
    "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
    "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12, "xiii": 13,
    "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19,
    "xx": 20,
}

def has_roman_numeral(s: str) -> bool:
    return bool(re.search(r'\b(?:I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV|XVI{0,3}|XIX|XX)\b', s, re.I))

def has_arabic_numeral_in_title(s: str) -> bool:
    return bool(re.search(r'\b\d{1,2}\b', s))

def has_parenthetical(s: str) -> bool:
    return bool(re.search(r'\(.*?\)', s))

def has_year_suffix(s: str) -> bool:
    return bool(re.search(r'\b(19|20)\d{2}\b', s))

def has_special_chars(s: str) -> bool:
    """Apostrophes, colons, hyphens, ampersands, etc. beyond simple alphanumeric+space."""
    return bool(re.search(r"[':\-&.!?\u2019\u2018]", s))

def has_subtitle(s: str) -> bool:
    """Detect colon-separated subtitles or dash-separated subtitles."""
    return bool(re.search(r':\s*\S', s))

def has_definite_article_prefix(s: str) -> bool:
    return bool(re.match(r'^(the|a|an)\s+', s, re.I))

def has_edition_suffix(s: str) -> bool:
    return bool(re.search(
        r"\b(gotY|game of the year|definitive|remaster|remake|deluxe|ultimate|"
        r"complete|enhanced|hd|collection|anniversary|legendary|gold|platinum|"
        r"director.s cut|special edition|expanded)\b", s, re.I))

def has_platform_in_title(s: str) -> bool:
    return bool(re.search(
        r"\b(ps[2-5]|psp|psv|ps vita|xbox|x360|xbone|xsx|xss|"
        r"switch|wii\s*u|wii|3ds|ds|gamecube|game boy|gba|"
        r"pc|steam|ios|android|vr|meta quest)\b", s, re.I))

def has_dlc_expansion_marker(s: str) -> bool:
    return bool(re.search(
        r"\b(dlc|expansion|expansion pass|season pass|chapter|episode|"
        r"act|part|mission pack|add.on|addon)\b", s, re.I))


# ---------------------------------------------------------------------------
# Categorize a single unmatched game
# ---------------------------------------------------------------------------

def categorize(title: str, slug: str) -> list[str]:
    """Return a list of category labels for this unmatched game."""
    cats = []
    norm = normalize_title(title)

    # Roman numeral mismatch potential: title has roman or arabic numerals
    if has_roman_numeral(title) or has_roman_numeral(slug):
        cats.append("roman_numeral_in_title")
    if has_arabic_numeral_in_title(title):
        cats.append("arabic_numeral_in_title")

    if has_parenthetical(title):
        cats.append("parenthetical_content")

    if has_year_suffix(title):
        cats.append("year_suffix_in_title")

    if has_special_chars(title):
        cats.append("special_characters")

    if has_subtitle(title):
        cats.append("subtitle_colon")

    if has_definite_article_prefix(title):
        cats.append("leading_article_the_a_an")

    if has_edition_suffix(title):
        cats.append("edition_variant_goty_remaster_etc")

    if has_platform_in_title(title):
        cats.append("platform_name_in_title")

    if has_dlc_expansion_marker(title):
        cats.append("dlc_expansion_or_episode")

    # Check if slug differs significantly from normalized title
    norm_slug = slug.replace("-", " ").strip() if slug else ""
    if norm and norm_slug and norm != norm_slug:
        # Try to see if the difference is just roman vs arabic
        roman_in_title = re.findall(r'\b(?:I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV|XVI{0,3}|XIX|XX)\b', title, re.I)
        arabic_in_slug = re.findall(r'\b\d+\b', norm_slug)
        if roman_in_title and arabic_in_slug:
            cats.append("roman_vs_arabic_numeral_mismatch")
        # And the reverse
        arabic_in_title = re.findall(r'\b\d+\b', title)
        roman_in_slug = re.findall(r'\b(?:I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV|XVI{0,3}|XIX|XX)\b', slug, re.I)
        if arabic_in_title and roman_in_slug:
            cats.append("roman_vs_arabic_numeral_mismatch")

    # Detect very short or very generic titles that are hard to match
    words = norm.split()
    if len(words) <= 1:
        cats.append("very_short_title_1_word")
    elif len(words) <= 2:
        cats.append("short_title_2_words")

    if not cats:
        cats.append("uncategorized")

    return cats


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Fetch unmatched games (platforms IS NULL)
    cur.execute("""
        SELECT
            g.game_id,
            g.title,
            g.release_year,
            gi.external_slug,
            gi.external_title,
            gi.source_name,
            gi.match_method,
            gi.match_confidence
        FROM games g
        LEFT JOIN game_identity gi ON gi.game_id = g.game_id
        WHERE g.platforms IS NULL
        ORDER BY g.title
    """)
    unmatched = cur.fetchall()
    total_unmatched = len(unmatched)
    print(f"{'='*80}")
    print(f" UNMATCHED GAMES ANALYSIS")
    print(f"{'='*80}")
    print(f"\nTotal unmatched games (platforms IS NULL): {total_unmatched}")

    # 2. Count reviews per game
    cur.execute("""
        SELECT game_id, COUNT(*) AS review_count
        FROM reviews
        GROUP BY game_id
    """)
    review_counts = {row["game_id"]: row["review_count"] for row in cur.fetchall()}

    # Also get external_baseline review_count for extra signal
    cur.execute("""
        SELECT game_id, SUM(review_count) AS total_ext_reviews
        FROM external_baseline
        GROUP BY game_id
    """)
    ext_review_counts = {row["game_id"]: row["total_ext_reviews"] for row in cur.fetchall()}

    # 3. Categorize every unmatched game
    category_games = defaultdict(list)  # category -> [(game_id, title, slug, review_count)]
    game_categories = {}  # game_id -> [categories]

    for row in unmatched:
        gid = row["game_id"]
        title = row["title"] or ""
        slug = row["external_slug"] or ""
        rc = review_counts.get(gid, 0)
        erc = ext_review_counts.get(gid, 0)
        combined_reviews = rc + erc

        cats = categorize(title, slug)
        game_categories[gid] = cats
        for c in cats:
            category_games[c].append((gid, title, slug, combined_reviews))

    # 4. Top 30 most-reviewed unmatched games
    review_list = []
    for row in unmatched:
        gid = row["game_id"]
        rc = review_counts.get(gid, 0)
        erc = ext_review_counts.get(gid, 0)
        review_list.append({
            "game_id": gid,
            "title": row["title"],
            "slug": row["external_slug"],
            "year": row["release_year"],
            "internal_reviews": rc,
            "external_reviews": erc,
            "total_reviews": rc + erc,
            "categories": game_categories.get(gid, []),
        })

    review_list.sort(key=lambda x: x["total_reviews"], reverse=True)

    print(f"\n{'='*80}")
    print(f" TOP 30 MOST-REVIEWED UNMATCHED GAMES")
    print(f"{'='*80}")
    print(f"{'#':>3}  {'Title':<50} {'Slug':<45} {'Year':>4} {'IntRev':>6} {'ExtRev':>6} {'Total':>6}  Categories")
    print("-" * 180)
    for i, g in enumerate(review_list[:30], 1):
        cats_str = ", ".join(g["categories"][:3])
        title_disp = (g["title"] or "")[:48]
        slug_disp = (g["slug"] or "N/A")[:43]
        year_disp = str(g["year"] or "")
        print(f"{i:3d}  {title_disp:<50} {slug_disp:<45} {year_disp:>4} {g['internal_reviews']:>6} {g['external_reviews']:>6} {g['total_reviews']:>6}  {cats_str}")

    # 5. Summary of failure categories
    print(f"\n{'='*80}")
    print(f" FAILURE CATEGORY SUMMARY")
    print(f"{'='*80}")
    print(f"\n(A game can belong to multiple categories)\n")

    CATEGORY_LABELS = {
        "roman_numeral_in_title":            "Roman numerals in title (II, III, IV, etc.)",
        "arabic_numeral_in_title":           "Arabic numerals in title (2, 3, 4, etc.)",
        "roman_vs_arabic_numeral_mismatch":  "Roman vs Arabic numeral mismatch (e.g. III vs 3)",
        "parenthetical_content":             "Parenthetical content (PS4), (2009), etc.",
        "year_suffix_in_title":              "Year suffix in title (e.g. 'FIFA 2009')",
        "special_characters":                "Special characters (apostrophes, colons, hyphens, &)",
        "subtitle_colon":                    "Colon-separated subtitle",
        "leading_article_the_a_an":          "Leading article (The, A, An)",
        "edition_variant_goty_remaster_etc": "Edition variant (GOTY, Remaster, Deluxe, HD, etc.)",
        "platform_name_in_title":            "Platform name in title (PS4, Xbox, Switch, etc.)",
        "dlc_expansion_or_episode":          "DLC / Expansion / Episode",
        "very_short_title_1_word":           "Very short title (1 word) -- hard to match",
        "short_title_2_words":               "Short title (2 words) -- ambiguous",
        "uncategorized":                     "Uncategorized -- no detected pattern",
    }

    sorted_cats = sorted(category_games.items(), key=lambda x: len(x[1]), reverse=True)
    print(f"{'Category':<48} {'Count':>6} {'%':>7}  Example titles")
    print("-" * 140)
    for cat, games in sorted_cats:
        label = CATEGORY_LABELS.get(cat, cat)
        cnt = len(games)
        pct = cnt / total_unmatched * 100 if total_unmatched else 0
        # Pick top 3 by review count as examples
        examples = sorted(games, key=lambda x: x[3], reverse=True)[:3]
        ex_str = " | ".join(e[1][:40] if e[1] else e[2][:40] for e in examples)
        print(f"{label:<48} {cnt:>6} {pct:>6.1f}%  {ex_str}")

    # 6. Deep dive: Roman vs Arabic mismatch examples
    print(f"\n{'='*80}")
    print(f" ROMAN vs ARABIC NUMERAL MISMATCH -- DETAILED EXAMPLES")
    print(f"{'='*80}")
    mismatch_games = category_games.get("roman_vs_arabic_numeral_mismatch", [])
    mismatch_games.sort(key=lambda x: x[3], reverse=True)
    for i, (gid, title, slug, rc) in enumerate(mismatch_games[:20], 1):
        print(f"  {i:3d}. {title:<55} -> slug: {slug}")

    # 7. Uncategorized sample -- these need manual inspection
    print(f"\n{'='*80}")
    print(f" UNCATEGORIZED GAMES (sample, sorted by reviews)")
    print(f"{'='*80}")
    uncategorized = category_games.get("uncategorized", [])
    uncategorized.sort(key=lambda x: x[3], reverse=True)
    for i, (gid, title, slug, rc) in enumerate(uncategorized[:30], 1):
        print(f"  {i:3d}. [{rc:>5} rev] {title:<55} -> slug: {slug or 'N/A'}")

    # 8. Source breakdown
    print(f"\n{'='*80}")
    print(f" UNMATCHED GAMES BY SOURCE")
    print(f"{'='*80}")
    source_counter = Counter()
    for row in unmatched:
        source_counter[row["source_name"] or "unknown"] += 1
    for src, cnt in source_counter.most_common():
        print(f"  {src:<35} {cnt:>6}  ({cnt/total_unmatched*100:.1f}%)")

    # 9. match_method breakdown (what was the last attempted method)
    print(f"\n{'='*80}")
    print(f" UNMATCHED GAMES BY LAST MATCH METHOD ATTEMPTED")
    print(f"{'='*80}")
    method_counter = Counter()
    for row in unmatched:
        method_counter[row["match_method"] or "none"] += 1
    for m, cnt in method_counter.most_common():
        print(f"  {m:<35} {cnt:>6}  ({cnt/total_unmatched*100:.1f}%)")

    conn.close()
    print(f"\n{'='*80}")
    print(f" ANALYSIS COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
