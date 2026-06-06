import { useState, useMemo } from "react";
import type { GameSummary } from "../lib/types";
import { useLang } from "../lib/i18n";
import { base } from "../lib/base";
import { GOTY_AWARDS, type YearData } from "../lib/awards-data";

interface Props {
  games: GameSummary[];
}

/* ── Fuzzy title matching ── */
function normalise(s: string): string {
  return s
    .toLowerCase()
    .replace(/[™®©]/g, "")
    .replace(/:\s*/g, " ")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function findGame(title: string, games: GameSummary[]): GameSummary | null {
  const n = normalise(title);
  // Exact normalised match
  const exact = games.find((g) => normalise(g.title) === n);
  if (exact) return exact;
  // Contains (e.g. "The Witcher 3" matches "The Witcher 3: Wild Hunt")
  const contains = games.find(
    (g) => normalise(g.title).includes(n) || n.includes(normalise(g.title)),
  );
  if (contains) return contains;
  // First-word match + year proximity
  const firstWord = n.split(" ")[0];
  if (firstWord.length >= 4) {
    const partial = games.find((g) => normalise(g.title).startsWith(firstWord));
    if (partial) return partial;
  }
  return null;
}

/* ── Award badge colours ── */
const SHOW_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  TGA: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
  BAFTA: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  GDC: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
};

export default function GotyList({ games }: Props) {
  const [, , t] = useLang();

  /* ── Build year map: IMS data per year ── */
  const imsByYear = useMemo(() => {
    const map = new Map<number, GameSummary[]>();
    games
      .filter((g) => g.release_year != null && g.ims_weighted != null)
      .forEach((g) => {
        const y = g.release_year!;
        if (!map.has(y)) map.set(y, []);
        map.get(y)!.push(g);
      });
    // Sort each year by ims_weighted desc
    map.forEach((list) => list.sort((a, b) => (b.ims_weighted ?? 0) - (a.ims_weighted ?? 0)));
    return map;
  }, [games]);

  /* ── Available years (intersection of award data and IMS data) ── */
  const years = useMemo(() => {
    return GOTY_AWARDS.filter((yd) => imsByYear.has(yd.year))
      .map((yd) => yd.year)
      .sort((a, b) => b - a);
  }, [imsByYear]);

  const [selectedYear, setSelectedYear] = useState(years[0] ?? 2024);

  const yearData = GOTY_AWARDS.find((y) => y.year === selectedYear) as YearData;
  const imsTop = (imsByYear.get(selectedYear) ?? []).slice(0, 10);

  /* ── Consensus analysis ── */
  const consensus = useMemo(() => {
    if (!yearData) return { count: 0, titles: new Map<string, string[]>() };
    const titleMap = new Map<string, string[]>();
    yearData.awards.forEach((a) => {
      const game = findGame(a.winner, games);
      const key = game?.title ?? a.winner;
      if (!titleMap.has(key)) titleMap.set(key, []);
      titleMap.get(key)!.push(a.show);
    });
    const multi = new Map<string, string[]>();
    titleMap.forEach((shows, title) => {
      if (shows.length >= 2) multi.set(title, shows);
    });
    return { count: multi.size, titles: multi };
  }, [yearData, games]);

  const fmt = (v: number | null) => (v != null ? v.toFixed(1) : "\u2014");

  if (years.length === 0) {
    return <p className="text-gray-500 text-center py-8">{t("goty.no_data")}</p>;
  }

  return (
    <div>
      {/* ─── Year selector ─── */}
      <div className="flex items-center gap-3 mb-6">
        <label className="text-sm font-medium text-gray-600 whitespace-nowrap">
          {t("goty.select_year")}
        </label>
        <select
          value={selectedYear}
          onChange={(e) => setSelectedYear(Number(e.target.value))}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-ims-400"
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      {/* ─── Award winners ─── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {yearData.awards.map((award) => {
          const style = SHOW_STYLES[award.show] ?? SHOW_STYLES.TGA;
          const matched = findGame(award.winner, games);
          return (
            <div
              key={award.show}
              className={`rounded-xl border p-4 ${style.bg} ${style.border}`}
            >
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-xs font-bold ${style.text}`}>
                  {award.show}
                </span>
                <span className="text-xs text-gray-400">
                  {t("goty.winner")}
                </span>
              </div>
              {matched ? (
                <a
                  href={`${base}/games/${matched.game_id}`}
                  className={`text-lg font-bold ${style.text} hover:underline block`}
                >
                  {matched.title}
                </a>
              ) : (
                <span className={`text-lg font-bold ${style.text} block`}>
                  {award.winner}
                </span>
              )}
              {matched && (
                <span className="text-xs text-gray-400 mt-1 block">
                  IMS {fmt(matched.ims_weighted)}
                </span>
              )}

              {/* Nominees (TGA only has detailed nominees) */}
              {award.nominees.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200/60">
                  <p className="text-xs text-gray-400 mb-1">
                    {t("goty.nominees")}
                  </p>
                  <ul className="text-xs text-gray-500 space-y-0.5">
                    {award.nominees.map((nom) => {
                      const nomGame = findGame(nom, games);
                      return (
                        <li key={nom}>
                          {nomGame ? (
                            <a
                              href={`${base}/games/${nomGame.game_id}`}
                              className="hover:text-ims-600"
                            >
                              {nom}
                            </a>
                          ) : (
                            nom
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ─── Consensus banner ─── */}
      {consensus.count > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6">
          <p className="text-sm font-medium text-yellow-800">
            &#x2B50; {t("goty.consensus")}
          </p>
          <p className="text-sm text-yellow-700 mt-1">
            {[...consensus.titles.entries()].map(([title, shows]) => (
              <span key={title} className="inline-block mr-4">
                <strong>{title}</strong> ({shows.join(" + ")})
              </span>
            ))}
          </p>
        </div>
      )}

      {/* ─── IMS Top 10 for this year ─── */}
      <h3 className="text-lg font-bold text-gray-800 mb-3">
        {t("goty.ims_top")} {selectedYear}
      </h3>

      {imsTop.length > 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-left">
              <tr>
                <th className="px-4 py-3 font-medium w-12">{t("col.rank")}</th>
                <th className="px-4 py-3 font-medium">{t("col.game")}</th>
                <th className="px-4 py-3 font-medium text-right">
                  {t("col.ims_weighted")}
                </th>
                <th className="px-4 py-3 font-medium text-right hidden sm:table-cell">
                  {t("col.metacritic")}
                </th>
                <th className="px-4 py-3 font-medium text-right hidden sm:table-cell">
                  {t("col.reviews")}
                </th>
              </tr>
            </thead>
            <tbody>
              {imsTop.map((g, i) => {
                // Check if this game won any award this year
                const wonAwards = yearData.awards
                  .filter((a) => {
                    const m = findGame(a.winner, games);
                    return m?.game_id === g.game_id;
                  })
                  .map((a) => a.show);

                return (
                  <tr
                    key={g.game_id}
                    className={`border-t border-gray-100 hover:bg-gray-50 ${
                      wonAwards.length > 0 ? "bg-yellow-50/50" : ""
                    }`}
                  >
                    <td className="px-4 py-2.5 text-gray-400 font-mono">
                      {i + 1}
                    </td>
                    <td className="px-4 py-2.5">
                      <a
                        href={`${base}/games/${g.game_id}`}
                        className="text-ims-700 hover:text-ims-500 font-medium"
                      >
                        {g.title}
                      </a>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {g.developer && <span>{g.developer}</span>}
                        {wonAwards.length > 0 && (
                          <span className="ml-2 text-yellow-600 font-medium">
                            &#x1F3C6; {wonAwards.join(" / ")} {t("goty.winner")}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-ims-700">
                      {fmt(g.ims_weighted)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-gray-600 hidden sm:table-cell">
                      {fmt(g.metacritic_score)}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-500 hidden sm:table-cell">
                      {g.review_count}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-400 text-sm py-4 text-center">
          {t("goty.no_ims_data")}
        </p>
      )}

      <p className="text-xs text-gray-400 mt-4 text-center">
        {t("goty.about")}
      </p>
    </div>
  );
}
