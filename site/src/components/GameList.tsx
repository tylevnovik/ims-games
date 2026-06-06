import { useState, useMemo } from "react";
import type { GameSummary } from "../lib/types";

interface Props {
  games: GameSummary[];
}

export default function GameList({ games }: Props) {
  const [search, setSearch] = useState("");
  const [yearFilter, setYearFilter] = useState<string>("");
  const [genreFilter, setGenreFilter] = useState<string>("");
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
    result = [...result].sort((a: any, b: any) => {
      const va = a[sortBy] ?? -1;
      const vb = b[sortBy] ?? -1;
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return result;
  }, [games, search, yearFilter, genreFilter, sortBy, sortDir]);

  const paged = filtered.slice(page * perPage, (page + 1) * perPage);
  const totalPages = Math.ceil(filtered.length / perPage);

  const fmt = (v: number | null) => (v != null ? v.toFixed(1) : "—");

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="text"
          placeholder="Search games..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-ims-400"
        />
        <select
          value={yearFilter}
          onChange={(e) => { setYearFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
        >
          <option value="">All Years</option>
          {allYears.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select
          value={genreFilter}
          onChange={(e) => { setGenreFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
        >
          <option value="">All Genres</option>
          {allGenres.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
        >
          <option value="ims_weighted">Sort: IMS Weighted</option>
          <option value="ims_raw">Sort: IMS Raw</option>
          <option value="ims_robust">Sort: IMS Robust</option>
          <option value="metacritic_score">Sort: Metacritic</option>
          <option value="review_count">Sort: Review Count</option>
          <option value="title">Sort: Title</option>
        </select>
        <button
          onClick={() => setSortDir(sortDir === "desc" ? "asc" : "desc")}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white hover:bg-gray-50"
        >
          {sortDir === "desc" ? "↓ Desc" : "↑ Asc"}
        </button>
      </div>

      <p className="text-sm text-gray-500 mb-3">{filtered.length.toLocaleString()} games found</p>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Game</th>
              <th className="px-4 py-3 font-medium">Year</th>
              <th className="px-4 py-3 font-medium text-right">MC</th>
              <th className="px-4 py-3 font-medium text-right">IMS Raw</th>
              <th className="px-4 py-3 font-medium text-right">IMS Weighted</th>
              <th className="px-4 py-3 font-medium text-right">Reviews</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((g) => (
              <tr key={g.game_id} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-2">
                  <a href={`/games/${g.game_id}`} className="text-ims-700 hover:text-ims-500 font-medium">
                    {g.title}
                  </a>
                  <div className="text-xs text-gray-400 mt-0.5">
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
          <button
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-sm text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages - 1}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
