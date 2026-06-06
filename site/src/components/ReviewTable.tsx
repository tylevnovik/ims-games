import { useState, useMemo } from "react";
import type { Review } from "../lib/types";
import { formatScore } from "../lib/score";
import { useLang } from "../lib/i18n";

interface Props {
  reviews: Review[];
}

export default function ReviewTable({ reviews }: Props) {
  const [lang, , t] = useLang();
  const [search, setSearch] = useState("");
  const [langFilter, setLangFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [sortBy, setSortBy] = useState<string>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const allLangs = useMemo(() => {
    const s = new Set<string>();
    reviews.forEach((r) => r.language && s.add(r.language));
    return [...s].sort();
  }, [reviews]);

  const allPlatforms = useMemo(() => {
    const s = new Set<string>();
    reviews.forEach((r) => r.platform && s.add(r.platform));
    return [...s].sort();
  }, [reviews]);

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  const sortIcon = (field: string) => {
    if (sortBy !== field) return <span className="text-gray-300 ml-1">⇅</span>;
    return <span className="text-ims-500 ml-1">{sortDir === "desc" ? "▼" : "▲"}</span>;
  };

  const stringFields = new Set(["source_name", "language", "date"]);

  const filtered = useMemo(() => {
    let result = reviews;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((r) => (r.source_name || "").toLowerCase().includes(q));
    }
    if (langFilter) {
      result = result.filter((r) => r.language === langFilter);
    }
    if (platformFilter) {
      result = result.filter((r) => r.platform === platformFilter);
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
  }, [reviews, search, langFilter, platformFilter, sortBy, sortDir]);

  if (!reviews.length) {
    return <p className="text-gray-500 text-sm">{t("review.none")}</p>;
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="text"
          placeholder={t("review.search_source")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-56 focus:outline-none focus:ring-2 focus:ring-ims-400"
        />
        {allLangs.length > 1 && (
          <select value={langFilter} onChange={(e) => setLangFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
            <option value="">{t("review.all_langs")}</option>
            {allLangs.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        )}
        {allPlatforms.length > 1 && (
          <select value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
            <option value="">{t("review.all_platforms")}</option>
            {allPlatforms.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        )}
      </div>

      {filtered.length < reviews.length && (
        <p className="text-sm text-gray-500 mb-3">{filtered.length} / {reviews.length} {t("review.showing")}</p>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-3 py-2 font-medium cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("source_name")}>
                {t("review.source")}{sortIcon("source_name")}
              </th>
              <th className="px-3 py-2 font-medium text-right cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("raw_score")}>
                {t("review.raw")}{sortIcon("raw_score")}
              </th>
              <th className="px-3 py-2 font-medium text-right cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("score")}>
                {t("review.normalized")}{sortIcon("score")}
              </th>
              <th className="px-3 py-2 font-medium text-right cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("weight")}>
                {t("review.weight")}{sortIcon("weight")}
              </th>
              <th className="px-3 py-2 font-medium cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("date")}>
                {t("review.date")}{sortIcon("date")}
              </th>
              <th className="px-3 py-2 font-medium cursor-pointer select-none hover:text-ims-600" onClick={() => toggleSort("language")}>
                {t("review.lang")}{sortIcon("language")}
              </th>
              <th className="px-3 py-2 font-medium">{t("review.summary")}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-3 py-2 font-medium text-gray-800 max-w-[150px]">
                  {r.source_name || "Unknown"}
                  {r.weight_explanation && (
                    <span title={r.weight_explanation} className="block text-xs text-gray-400 cursor-help truncate max-w-[150px]">
                      {r.weight_explanation}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono text-gray-600">{r.raw_score != null ? r.raw_score : "—"}</td>
                <td className="px-3 py-2 text-right font-mono font-bold">{formatScore(r.score)}</td>
                <td className="px-3 py-2 text-right font-mono text-gray-500">{r.weight != null ? r.weight.toFixed(3) : "—"}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{r.date || "—"}</td>
                <td className="px-3 py-2 text-gray-500">{r.language || "—"}</td>
                <td className="px-3 py-2 text-gray-600 max-w-[300px] truncate">
                  {r.summary ? <span title={r.summary}>{r.summary.length > 100 ? r.summary.slice(0, 100) + "..." : r.summary}</span> : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
