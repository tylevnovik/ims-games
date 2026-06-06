import { useState, useMemo } from "react";
import type { GameSummary } from "../lib/types";
import { useLang } from "../lib/i18n";
import { base } from "../lib/base";

interface Props {
  games: GameSummary[];
}

export default function GameList({ games }: Props) {
  const [lang, , t] = useLang();
  const [search, setSearch] = useState("");
  const [yearFilter, setYearFilter] = useState<string>("");
  const [genreFilter, setGenreFilter] = useState<string>("");
  const [platformFilter, setPlatformFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("ims_weighted");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const perPage = 50;

  const allYears = useMemo(() => {
    const years = new Set<number>();
    games.forEach((g) => g.release_year && years.add(g.release_year));
    return [...years].sort((a, b) => b - a);
  }, [games]);

  const allGenres = useMemo(() => {
    const genres = new Set<string>();
    games.forEach((g) => (g.genres || []).forEach((x) => genres.add(x)));
    return [...genres].sort();
  }, [games]);

  const allPlatforms = useMemo(() => {
    const plats = new Set<string>();
    games.forEach((g) => (g.platforms || []).forEach((p) => plats.add(p)));
    return [...plats].sort();
  }, [games]);

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    setPage(0);
  };

  const sortIcon = (field: string) => {
    if (sortBy !== field) return <span className="text-gray-300 ml-1">⇅</span>;
    return <span className="text-ims-500 ml-1">{sortDir === "desc" ? "▼" : "▲"}</span>;
  };

  const stringFields = new Set(["title"]);

  const filtered = useMemo(() => {
    let result = games;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((g) => g.title.toLowerCase().includes(q));
    }
    if (yearFilter) {
      result = result.filter((g) => g.release_year === Number(yearFilter));
    }
    if (genreFilter) {
      result = result.filter((g) => (g.genres || []).includes(genreFilter));
    }
    if (platformFilter) {
      result = result.filter((g) => (g.platforms || []).includes(platformFilter));
    }
    result = [...result].sort((a: any, b: any) => {
      if (stringFields.has(sortBy)) {
        const va = (a[sortBy] ?? "") as string;
        const vb = (b[sortBy] ?? "") as string;
        return sortDir === "desc" ? vb.localeCompare(va) : va.localeCompare(vb);
      }
      const va = a[sortBy] ?? -1;
      const vb = b[sortBy] ?? -1;
      return sortDir === "desc" ? (vb as number) - (va as number) : (va as number) - (vb as number);
    });
    return result;
  }, [games, search, yearFilter, genreFilter, platformFilter, sortBy, sortDir]);

  const paged = filtered.slice(page * perPage, (page + 1) * perPage);
  const totalPages = Math.ceil(filtered.length / perPage);

  const fmt = (v: number | null) => (v != null ? v.toFixed(1) : "—");

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="text"
          placeholder={t("games.search")}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-full sm:w-64 focus:outline-none focus:ring-2 focus:ring-ims-400"
        />
        <select value={yearFilter} onChange={(e) => { setYearFilter(e.target.value); setPage(0); }} className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
          <option value="">{t("games.all_years")}</option>
          {allYears.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select value={genreFilter} onChange={(e) => { setGenreFilter(e.target.value); setPage(0); }} className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
          <option value="">{t("games.all_genres")}</option>
          {allGenres.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <select value={platformFilter} onChange={(e) => { setPlatformFilter(e.target.value); setPage(0); }} className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
          <option value="">{t("games.all_platforms")}</option>
          {allPlatforms.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      <p className="text-sm text-gray-500 mb-3">{filtered.length.toLocaleString()} {t("games.found")}</p>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-4 py-3 font-medium cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("title")}>{t("col.game")}{sortIcon("title")}</th>
              <th className="px-4 py-3 font-medium cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("release_year")}>{t("col.year")}{sortIcon("release_year")}</th>
              <th className="px-4 py-3 font-medium cursor-pointer select-none hover:text-ims-600 text-right" onClick={() => toggleSort("metacritic_score")}>{t("col.metacritic")}{sortIcon("metacritic_score")}</th>
              <th className="px-4 py-3 font-medium cursor-pointer select-none hover:text-ims-600 text-right" onClick={() => toggleSort("ims_raw")}>{t("col.ims_raw")}{sortIcon("ims_raw")}</th>
              <th className="px-4 py-3 font-medium cursor-pointer select-none hover:text-ims-600 text-right" onClick={() => toggleSort("ims_weighted")}>{t("col.ims_weighted")}{sortIcon("ims_weighted")}</th>
              <th className="px-4 py-3 font-medium cursor-pointer select-none hover:text-ims-600 text-right" onClick={() => toggleSort("review_count")}>{t("col.reviews")}{sortIcon("review_count")}</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((g) => (
              <tr key={g.game_id} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-2">
                  <a href={`${base}/games/${g.game_id}`} className="text-ims-700 hover:text-ims-500 font-medium">{g.title}</a>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {g.developer && <span>{g.developer}</span>}
                    {g.developer && (g.genres || []).length > 0 && <span> &middot; </span>}
                    {(g.genres || []).slice(0, 2).join(", ")}
                  </div>
                </td>
                <td className="px-4 py-2 text-gray-500">{g.release_year || "—"}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-600">{fmt(g.metacritic_score)}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-600">{fmt(g.ims_raw)}</td>
                <td className="px-4 py-2 text-right font-mono font-bold text-ims-700">{fmt(g.ims_weighted)}</td>
                <td className="px-4 py-2 text-right text-gray-500">{g.review_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button disabled={page === 0} onClick={() => setPage(page - 1)} className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-40">
            {t("games.prev")}
          </button>
          <span className="text-sm text-gray-500">{t("games.page", [page + 1, totalPages])}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)} className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-40">
            {t("games.next")}
          </button>
        </div>
      )}
    </div>
  );
}
