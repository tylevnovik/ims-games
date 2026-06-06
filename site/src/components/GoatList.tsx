import { useMemo } from "react";
import type { GameSummary } from "../lib/types";
import { useLang } from "../lib/i18n";
import { base } from "../lib/base";

interface Props {
  games: GameSummary[];
}

export default function GoatList({ games }: Props) {
  const [, , t] = useLang();

  const ranked = useMemo(
    () =>
      games
        .filter((g) => g.ims_weighted != null)
        .sort((a, b) => (b.ims_weighted ?? 0) - (a.ims_weighted ?? 0)),
    [games],
  );

  if (ranked.length === 0) {
    return <p className="text-gray-500 text-center py-8">{t("goat.no_data")}</p>;
  }

  const goat = ranked[0];
  const runners = ranked.slice(1, 30);
  const fmt = (v: number | null) => (v != null ? v.toFixed(1) : "\u2014");

  /* ── Score badge colour helper ── */
  const scoreColor = (s: number) => {
    if (s >= 95) return "text-yellow-500";
    if (s >= 90) return "text-green-600";
    if (s >= 80) return "text-ims-700";
    return "text-gray-600";
  };

  return (
    <div>
      {/* ─── #1 GOAT Hero ─── */}
      <div className="bg-gradient-to-br from-yellow-50 to-amber-50 border border-yellow-300 rounded-2xl p-6 sm:p-8 mb-8 text-center">
        <div className="text-5xl mb-3" aria-hidden="true">
          &#x1F3C6;
        </div>
        <p className="text-xs sm:text-sm font-bold tracking-widest text-yellow-600 uppercase mb-2">
          {t("goat.title")}
        </p>
        <a
          href={`${base}/games/${goat.game_id}`}
          className="block text-2xl sm:text-4xl font-bold text-gray-900 hover:text-ims-600 transition-colors mb-2"
        >
          {goat.title}
        </a>
        <p className="text-gray-500 text-sm mb-4">
          {[
            goat.developer,
            goat.release_year && `(${goat.release_year})`,
          ]
            .filter(Boolean)
            .join(" ")}
        </p>

        {/* Key stats */}
        <div className="flex flex-wrap justify-center gap-4 sm:gap-6 text-sm">
          <div>
            <span className="text-2xl font-bold text-ims-700">
              {fmt(goat.ims_weighted)}
            </span>
            <br />
            <span className="text-gray-400">{t("col.ims_weighted")}</span>
          </div>
          <div>
            <span className="text-2xl font-bold text-gray-600">
              {fmt(goat.ims_raw)}
            </span>
            <br />
            <span className="text-gray-400">{t("col.ims_raw")}</span>
          </div>
          <div>
            <span className="text-2xl font-bold text-gray-600">
              {fmt(goat.metacritic_score)}
            </span>
            <br />
            <span className="text-gray-400">{t("col.metacritic")}</span>
          </div>
          <div>
            <span className="text-2xl font-bold text-gray-600">
              {goat.review_count}
            </span>
            <br />
            <span className="text-gray-400">{t("col.reviews")}</span>
          </div>
        </div>

        {goat.description && (
          <p className="mt-4 text-sm text-gray-500 max-w-xl mx-auto line-clamp-3">
            {goat.description}
          </p>
        )}
      </div>

      {/* ─── Runners-up Table ─── */}
      <h2 className="text-xl font-bold text-gray-800 mb-4">
        {t("goat.candidates")}
      </h2>

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
                {t("col.ims_raw")}
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
            {runners.map((g, i) => (
              <tr
                key={g.game_id}
                className="border-t border-gray-100 hover:bg-gray-50"
              >
                <td className="px-4 py-2.5 text-gray-400 font-mono">
                  {i + 2}
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
                    {g.developer && g.release_year && (
                      <span> &middot; </span>
                    )}
                    {g.release_year && <span>{g.release_year}</span>}
                  </div>
                </td>
                <td
                  className={`px-4 py-2.5 text-right font-mono font-bold ${scoreColor(g.ims_weighted ?? 0)}`}
                >
                  {fmt(g.ims_weighted)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-600 hidden sm:table-cell">
                  {fmt(g.ims_raw)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-600 hidden sm:table-cell">
                  {fmt(g.metacritic_score)}
                </td>
                <td className="px-4 py-2.5 text-right text-gray-500 hidden sm:table-cell">
                  {g.review_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400 mt-3 text-center">
        {t("goat.based_on")}
      </p>
    </div>
  );
}
