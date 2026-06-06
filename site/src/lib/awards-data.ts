/**
 * Historical Game of the Year award data from major award shows.
 *
 * TGA  = The Game Awards (Dec, since 2014)
 * BAFTA = British Academy Games Award for Best Game (Mar/Apr, since 2004)
 * GDC  = Game Developers Choice Award for Game of the Year (Mar, since 2001)
 *
 * Each year records the winner and nominees per award show.
 */

export interface AwardEntry {
  show: "TGA" | "BAFTA" | "GDC";
  winner: string;
  nominees: string[];
}

export interface YearData {
  year: number;
  awards: AwardEntry[];
}

export const GOTY_AWARDS: YearData[] = [
  // ── 2014 ──────────────────────────────────────────────
  {
    year: 2014,
    awards: [
      {
        show: "TGA",
        winner: "Dragon Age: Inquisition",
        nominees: ["Bayonetta 2", "Dark Souls II", "Hearthstone", "Middle-earth: Shadow of Mordor"],
      },
      {
        show: "BAFTA",
        winner: "Destiny",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Middle-earth: Shadow of Mordor",
        nominees: [],
      },
    ],
  },
  // ── 2015 ──────────────────────────────────────────────
  {
    year: 2015,
    awards: [
      {
        show: "TGA",
        winner: "The Witcher 3: Wild Hunt",
        nominees: ["Bloodborne", "Fallout 4", "Metal Gear Solid V: The Phantom Pain", "Super Mario Maker"],
      },
      {
        show: "BAFTA",
        winner: "Fallout 4",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "The Witcher 3: Wild Hunt",
        nominees: [],
      },
    ],
  },
  // ── 2016 ──────────────────────────────────────────────
  {
    year: 2016,
    awards: [
      {
        show: "TGA",
        winner: "Overwatch",
        nominees: ["Doom", "Inside", "Titanfall 2", "Uncharted 4: A Thief's End"],
      },
      {
        show: "BAFTA",
        winner: "Uncharted 4: A Thief's End",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Overwatch",
        nominees: [],
      },
    ],
  },
  // ── 2017 ──────────────────────────────────────────────
  {
    year: 2017,
    awards: [
      {
        show: "TGA",
        winner: "The Legend of Zelda: Breath of the Wild",
        nominees: ["Horizon Zero Dawn", "Persona 5", "PUBG: Battlegrounds", "Super Mario Odyssey"],
      },
      {
        show: "BAFTA",
        winner: "What Remains of Edith Finch",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "The Legend of Zelda: Breath of the Wild",
        nominees: [],
      },
    ],
  },
  // ── 2018 ──────────────────────────────────────────────
  {
    year: 2018,
    awards: [
      {
        show: "TGA",
        winner: "God of War",
        nominees: [
          "Assassin's Creed Odyssey",
          "Celeste",
          "Marvel's Spider-Man",
          "Monster Hunter: World",
          "Red Dead Redemption 2",
        ],
      },
      {
        show: "BAFTA",
        winner: "God of War",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "God of War",
        nominees: [],
      },
    ],
  },
  // ── 2019 ──────────────────────────────────────────────
  {
    year: 2019,
    awards: [
      {
        show: "TGA",
        winner: "Sekiro: Shadows Die Twice",
        nominees: [
          "Control",
          "Death Stranding",
          "Resident Evil 2",
          "Super Smash Bros. Ultimate",
          "The Outer Worlds",
        ],
      },
      {
        show: "BAFTA",
        winner: "Outer Wilds",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Untitled Goose Game",
        nominees: [],
      },
    ],
  },
  // ── 2020 ──────────────────────────────────────────────
  {
    year: 2020,
    awards: [
      {
        show: "TGA",
        winner: "The Last of Us Part II",
        nominees: [
          "Animal Crossing: New Horizons",
          "Doom Eternal",
          "Final Fantasy VII Remake",
          "Ghost of Tsushima",
          "Hades",
        ],
      },
      {
        show: "BAFTA",
        winner: "Hades",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Hades",
        nominees: [],
      },
    ],
  },
  // ── 2021 ──────────────────────────────────────────────
  {
    year: 2021,
    awards: [
      {
        show: "TGA",
        winner: "It Takes Two",
        nominees: [
          "Deathloop",
          "Metroid Dread",
          "Psychonauts 2",
          "Ratchet & Clank: Rift Apart",
          "Resident Evil Village",
        ],
      },
      {
        show: "BAFTA",
        winner: "Returnal",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Inscryption",
        nominees: [],
      },
    ],
  },
  // ── 2022 ──────────────────────────────────────────────
  {
    year: 2022,
    awards: [
      {
        show: "TGA",
        winner: "Elden Ring",
        nominees: [
          "A Plague Tale: Requiem",
          "God of War Ragnarök",
          "Horizon Forbidden West",
          "Stray",
          "Xenoblade Chronicles 3",
        ],
      },
      {
        show: "BAFTA",
        winner: "Vampire Survivors",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Elden Ring",
        nominees: [],
      },
    ],
  },
  // ── 2023 ──────────────────────────────────────────────
  {
    year: 2023,
    awards: [
      {
        show: "TGA",
        winner: "Baldur's Gate 3",
        nominees: [
          "Alan Wake 2",
          "The Legend of Zelda: Tears of the Kingdom",
          "Marvel's Spider-Man 2",
          "Resident Evil 4",
          "Super Mario Bros. Wonder",
        ],
      },
      {
        show: "BAFTA",
        winner: "Baldur's Gate 3",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Baldur's Gate 3",
        nominees: [],
      },
    ],
  },
  // ── 2024 ──────────────────────────────────────────────
  {
    year: 2024,
    awards: [
      {
        show: "TGA",
        winner: "Astro Bot",
        nominees: [
          "Balatro",
          "Black Myth: Wukong",
          "Elden Ring: Shadow of the Erdtree",
          "Final Fantasy VII Rebirth",
          "Metaphor: ReFantazio",
        ],
      },
      {
        show: "BAFTA",
        winner: "Astro Bot",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Balatro",
        nominees: [],
      },
    ],
  },
  // ── 2025 ──────────────────────────────────────────────
  {
    year: 2025,
    awards: [
      {
        show: "TGA",
        winner: "Clair Obscur: Expedition 33",
        nominees: [
          "Death Stranding 2",
          "Donkey Kong Bananza",
          "Hades II",
          "Hollow Knight: Silksong",
          "Kingdom Come: Deliverance II",
        ],
      },
      {
        show: "BAFTA",
        winner: "Clair Obscur: Expedition 33",
        nominees: [],
      },
      {
        show: "GDC",
        winner: "Clair Obscur: Expedition 33",
        nominees: [],
      },
    ],
  },
];

/** All unique game titles mentioned across every award (for matching). */
export const ALL_AWARD_TITLES: string[] = (() => {
  const set = new Set<string>();
  for (const y of GOTY_AWARDS) {
    for (const a of y.awards) {
      set.add(a.winner);
      a.nominees.forEach((n) => set.add(n));
    }
  }
  return [...set].sort();
})();
