"""Canonical source naming helpers shared by importers."""

import hashlib
import re


SOURCE_NAME_ALIASES = {
    "ign": "IGN",
    "ign.com": "IGN",
    "gamespot": "GameSpot",
    "game spot": "GameSpot",
    "game informer": "Game Informer",
    "gameinformer": "Game Informer",
    "action trip": "ActionTrip",
    "actiontrip": "ActionTrip",
    "finger guns": "Finger Guns",
    "fingerguns": "Finger Guns",
    "firing squad": "Firing Squad",
    "firingsquad": "Firing Squad",
    "game critics": "GameCritics",
    "gamecritics": "GameCritics",
    "game rant": "Game Rant",
    "gamerant": "Game Rant",
    "gamers' temple": "Gamers' Temple",
    "gamers\\' temple": "Gamers' Temple",
    "pc gamer": "PC Gamer",
    "pcgamer": "PC Gamer",
    "games radar": "GamesRadar+",
    "gamesradar": "GamesRadar+",
    "gamesradar+": "GamesRadar+",
    "eurogamer": "Eurogamer",
    "destructoid": "Destructoid",
    "polygon": "Polygon",
    "kotaku": "Kotaku",
    "the guardian": "The Guardian",
    "vg247": "VG247",
    "nintendo life": "Nintendo Life",
    "push square": "Push Square",
    "rock paper shotgun": "Rock Paper Shotgun",
    "rockpapershotgun": "Rock Paper Shotgun",
    "comicbook.com": "Comicbook.com",
    "darkstation": "DarkStation",
    "fandom": "Fandom",
    "play zine": "PLAY! Zine",
    "play! zine": "PLAY! Zine",
    "ragequit.gr": "Ragequit.gr",
    "spaziogames": "SpazioGames",
    "trusted reviews": "Trusted Reviews",
    "trustedreviews": "Trusted Reviews",
}


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def canonical_source_name(name: str) -> str:
    """Return the canonical display name for a media outlet."""
    cleaned = re.sub(r"\s+", " ", str(name or "")).strip()
    if not cleaned:
        return "Unknown Source"
    key = cleaned.lower().replace("&amp;", "&")
    key = re.sub(r"https?://(www\.)?", "", key).strip("/")
    key = key.replace("www.", "")
    return SOURCE_NAME_ALIASES.get(key, cleaned)


def source_id_for_name(name: str) -> str:
    """Stable source id shared across Metacritic/OpenCritic importers.

    Keep the historical ``mc-src`` prefix so exact-name Metacritic rows keep
    their existing IDs, while newer importers can merge into the same source.
    """
    canonical = canonical_source_name(name)
    return f"mc-src-{_md5(canonical)[:12]}"
