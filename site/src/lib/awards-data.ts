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
        nominees: [
          "Middle-earth: Shadow of Mordor",
          "Monument Valley",
          "Mario Kart 8",
          "Dragon Age: Inquisition",
          "Alien: Isolation",
        ],
      },
      {
        show: "GDC",
        winner: "Middle-earth: Shadow of Mordor",
        nominees: ["Bayonetta 2", "Destiny", "Hearthstone: Heroes of Warcraft", "Alien: Isolation"],
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
        nominees: [
          "Everybody's Gone to the Rapture",
          "Life is Strange",
          "Metal Gear Solid V: The Phantom Pain",
          "Rocket League",
          "The Witcher 3: Wild Hunt",
        ],
      },
      {
        show: "GDC",
        winner: "The Witcher 3: Wild Hunt",
        nominees: ["Fallout 4", "Metal Gear Solid V: The Phantom Pain", "Bloodborne", "Rocket League"],
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
        nominees: ["Stardew Valley", "Titanfall 2", "Firewatch", "Inside", "Overwatch"],
      },
      {
        show: "GDC",
        winner: "Overwatch",
        nominees: ["Uncharted 4: A Thief's End", "Inside", "Dishonored 2", "Firewatch"],
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
        nominees: [
          "Assassin's Creed Origins",
          "Hellblade: Senua's Sacrifice",
          "Horizon Zero Dawn",
          "The Legend of Zelda: Breath of the Wild",
          "Super Mario Odyssey",
        ],
      },
      {
        show: "GDC",
        winner: "The Legend of Zelda: Breath of the Wild",
        nominees: ["PUBG: Battlegrounds", "NieR: Automata", "Horizon Zero Dawn", "Super Mario Odyssey"],
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
        nominees: [
          "Assassin's Creed Odyssey",
          "Astro Bot Rescue Mission",
          "Celeste",
          "Red Dead Redemption 2",
          "Return of the Obra Dinn",
        ],
      },
      {
        show: "GDC",
        winner: "God of War",
        nominees: ["Red Dead Redemption 2", "Return of the Obra Dinn", "Marvel's Spider-Man", "Celeste"],
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
        nominees: [
          "Untitled Goose Game",
          "Control",
          "Disco Elysium",
          "Luigi's Mansion 3",
          "Sekiro: Shadows Die Twice",
        ],
      },
      {
        show: "GDC",
        winner: "Untitled Goose Game",
        nominees: ["Death Stranding", "Control", "Sekiro: Shadows Die Twice", "Outer Wilds"],
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
        nominees: [
          "Animal Crossing: New Horizons",
          "Ghost of Tsushima",
          "Half-Life: Alyx",
          "Marvel's Spider-Man: Miles Morales",
          "The Last of Us Part II",
        ],
      },
      {
        show: "GDC",
        winner: "Hades",
        nominees: [
          "Animal Crossing: New Horizons",
          "The Last of Us Part II",
          "Half-Life: Alyx",
          "Ghost of Tsushima",
        ],
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
        nominees: ["Inscryption", "It Takes Two", "Ratchet & Clank: Rift Apart", "Deathloop", "Forza Horizon 5"],
      },
      {
        show: "GDC",
        winner: "Inscryption",
        nominees: ["Forza Horizon 5", "Resident Evil Village", "Deathloop", "It Takes Two"],
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
        nominees: ["Cult of the Lamb", "Elden Ring", "God of War Ragnarök", "Marvel Snap", "Stray"],
      },
      {
        show: "GDC",
        winner: "Elden Ring",
        nominees: ["God of War Ragnarök", "Immortality", "Pentiment", "Stray", "Tunic"],
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
        nominees: [
          "Alan Wake 2",
          "Dave the Diver",
          "Marvel's Spider-Man 2",
          "Super Mario Bros. Wonder",
          "The Legend of Zelda: Tears of the Kingdom",
        ],
      },
      {
        show: "GDC",
        winner: "Baldur's Gate 3",
        nominees: [
          "Cocoon",
          "Dave the Diver",
          "Dredge",
          "Marvel's Spider-Man 2",
          "The Legend of Zelda: Tears of the Kingdom",
        ],
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
        nominees: [
          "Balatro",
          "Black Myth: Wukong",
          "Helldivers 2",
          "The Legend of Zelda: Echoes of Wisdom",
          "Thank Goodness You're Here!",
        ],
      },
      {
        show: "GDC",
        winner: "Balatro",
        nominees: [
          "Astro Bot",
          "Black Myth: Wukong",
          "Final Fantasy VII Rebirth",
          "Helldivers 2",
          "Metaphor: ReFantazio",
        ],
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
          "Death Stranding 2: On the Beach",
          "Donkey Kong Bananza",
          "Hades II",
          "Hollow Knight: Silksong",
          "Kingdom Come: Deliverance II",
        ],
      },
      {
        show: "BAFTA",
        winner: "Clair Obscur: Expedition 33",
        nominees: [
          "Arc Raiders",
          "Blue Prince",
          "Dispatch",
          "Ghost of Yotei",
          "Indiana Jones and the Great Circle",
        ],
      },
      {
        show: "GDC",
        winner: "Clair Obscur: Expedition 33",
        nominees: [
          "Blue Prince",
          "Donkey Kong Bananza",
          "Ghost of Yotei",
          "Hollow Knight: Silksong",
          "Split Fiction",
        ],
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
