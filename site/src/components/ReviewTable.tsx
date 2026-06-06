import type { Review } from "../lib/types";
import { formatScore } from "../lib/score";
import { useLang } from "../lib/i18n";

interface Props {
  reviews: Review[];
}

export default function ReviewTable({ reviews }: Props) {
  const [lang, , t] = useLang();

  if (!reviews.length) {
    return <p className="text-gray-500 text-sm">{t("review.none")}</p>;
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-left">
          <tr>
            <th className="px-3 py-2 font-medium">{t("review.source")}</th>
            <th className="px-3 py-2 font-medium text-right">{t("review.raw")}</th>
            <th className="px-3 py-2 font-medium text-right">{t("review.normalized")}</th>
            <th className="px-3 py-2 font-medium text-right">{t("review.weight")}</th>
            <th className="px-3 py-2 font-medium">{t("review.date")}</th>
            <th className="px-3 py-2 font-medium">{t("review.lang")}</th>
            <th className="px-3 py-2 font-medium">{t("review.summary")}</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((r, i) => (
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
  );
}
