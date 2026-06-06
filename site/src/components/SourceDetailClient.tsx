import { useState, useEffect } from "react";
import type { SourceDetail } from "../lib/types";
import { formatScore } from "../lib/score";
import { useLang } from "../lib/i18n";

interface Props {
  sourceId: string;
}

export default function SourceDetailClient({ sourceId }: Props) {
  const [lang, , t] = useLang();
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetch(`${import.meta.env.BASE_URL}data/sources/${sourceId}.json`)
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data) => { setSource(data); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [sourceId]);

  if (loading) {
    return (
      <div className="text-center py-20 text-gray-500">
        <div className="animate-spin w-8 h-8 border-4 border-ims-400 border-t-transparent rounded-full mx-auto mb-4" />
        <p>{t("game.loading")}</p>
      </div>
    );
  }

  if (error || !source) {
    return <p className="text-center py-20 text-red-500">{t("game.load_error")}</p>;
  }

  const m = source.metrics || {};

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">{source.name}</h1>
        <div className="flex flex-wrap gap-3 mt-2 text-sm text-gray-500">
          {source.source_type && <span className="px-2 py-0.5 bg-gray-100 rounded">{source.source_type}</span>}
          {source.language && <span className="px-2 py-0.5 bg-ims-50 text-ims-700 rounded">{source.language}</span>}
          {source.country_region && <span>{source.country_region}</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-gray-800">{source.review_count.toLocaleString()}</div>
          <div className="text-xs text-gray-500 mt-1">{t("source.total_reviews")}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-gray-800">{formatScore(m.mean_score as number)}</div>
          <div className="text-xs text-gray-500 mt-1">{t("source.avg_score")}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-gray-800">{formatScore(m.score_std as number)}</div>
          <div className="text-xs text-gray-500 mt-1">{t("source.std_dev")}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-gray-800">
            {m.score_bias != null ? ((m.score_bias as number) > 0 ? "+" : "") + (m.score_bias as number).toFixed(1) : t("score.na")}
          </div>
          <div className="text-xs text-gray-500 mt-1">{t("source.score_bias")}</div>
        </div>
      </div>

      {/* Weight info */}
      {source.weights && "records" in source.weights && (source.weights as any).records.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-8">
          <h2 className="text-lg font-bold text-gray-800 mb-3">{t("source.weight_breakdown")}</h2>
          <div className="space-y-2 text-sm">
            {(source.weights as any).records.slice(0, 10).map((w: any, i: number) => (
              <div key={i} className="flex items-start gap-3 border-b border-gray-50 pb-2">
                <div className="font-mono font-bold text-ims-700 w-16 text-right">
                  {w.context_weight != null ? w.context_weight.toFixed(3) : "—"}
                </div>
                <div className="text-gray-600">
                  {w.genre && <span className="px-1.5 py-0.5 bg-ims-50 text-ims-700 rounded text-xs mr-1">{w.genre}</span>}
                  {w.platform && <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs mr-1">{w.platform}</span>}
                  {w.explanation && <span className="text-gray-500 text-xs">{w.explanation}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent reviews */}
      {source.recent_reviews && source.recent_reviews.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-8">
          <h2 className="text-lg font-bold text-gray-800 mb-3">{t("source.recent_reviews")}</h2>
          <table className="w-full text-sm">
            <thead className="text-gray-600 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">{t("col.game")}</th>
                <th className="px-3 py-2 font-medium text-right">{t("review.normalized")}</th>
                <th className="px-3 py-2 font-medium">{t("review.date")}</th>
              </tr>
            </thead>
            <tbody>
              {source.recent_reviews.map((r, i) => (
                <tr key={i} className="border-t border-gray-100">
                  <td className="px-3 py-2">
                    <a href={`${import.meta.env.BASE_URL}games/${r.game_id}`} className="text-ims-700 hover:text-ims-500">{r.game_title}</a>
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-bold">{formatScore(r.score)}</td>
                  <td className="px-3 py-2 text-gray-500">{r.date || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Coverage */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-bold text-gray-700 mb-3">{t("source.genre_coverage")}</h3>
          <div className="space-y-1 text-sm">
            {Object.entries(source.genre_coverage || {})
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .slice(0, 15)
              .map(([genre, count]) => (
                <div key={genre} className="flex justify-between">
                  <span className="text-gray-600">{genre}</span>
                  <span className="text-gray-400">{count}</span>
                </div>
              ))}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-bold text-gray-700 mb-3">{t("source.platform_coverage")}</h3>
          <div className="space-y-1 text-sm">
            {Object.entries(source.platform_coverage || {})
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .slice(0, 15)
              .map(([plat, count]) => (
                <div key={plat} className="flex justify-between">
                  <span className="text-gray-600">{plat}</span>
                  <span className="text-gray-400">{count}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
