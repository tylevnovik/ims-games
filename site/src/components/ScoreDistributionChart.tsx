import { useMemo } from "react";
import type { Review } from "../lib/types";
import { useLang } from "../lib/i18n";

interface Props {
  reviews: Review[];
}

export default function ScoreDistributionChart({ reviews }: Props) {
  const [lang, , t] = useLang();

  const { buckets, maxCount, totalScores, meanScore } = useMemo(() => {
    const scores = reviews.filter((r) => r.score != null).map((r) => r.score!);
    if (!scores.length) return { buckets: [], maxCount: 0, totalScores: 0, meanScore: 0 };

    const bucketSize = 10;
    const counts: { lo: number; hi: number; count: number }[] = [];
    for (let i = 0; i < 100; i += bucketSize) {
      const lo = i;
      const hi = i + bucketSize;
      // Last bucket is inclusive of 100
      const count = i === 90
        ? scores.filter((s) => s >= lo && s <= hi).length
        : scores.filter((s) => s >= lo && s < hi).length;
      counts.push({ lo, hi, count });
    }

    const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
    return {
      buckets: counts,
      maxCount: Math.max(...counts.map((c) => c.count), 1),
      totalScores: scores.length,
      meanScore: Math.round(mean * 10) / 10,
    };
  }, [reviews]);

  if (!buckets.length || buckets.every((b) => b.count === 0)) {
    return <p className="text-gray-500 text-sm text-center py-8">{t("chart.no_data")}</p>;
  }

  const colors = [
    "bg-red-400", "bg-red-300", "bg-orange-400", "bg-orange-300",
    "bg-yellow-400", "bg-yellow-300", "bg-lime-400", "bg-green-400",
    "bg-emerald-500", "bg-green-600",
  ];

  return (
    <div>
      {/* Bars */}
      <div className="flex items-end gap-0.5 h-28">
        {buckets.map((b, i) => {
          const pct = (b.count / maxCount) * 100;
          return (
            <div key={i} className="flex-1 flex flex-col items-center group relative">
              <div
                className={`w-full ${colors[i]} rounded-t-sm transition-all duration-200`}
                style={{
                  height: `${Math.max(pct, b.count > 0 ? 3 : 0)}%`,
                }}
              />
              {/* Tooltip */}
              <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 touch:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                {b.lo}-{b.hi}: {b.count} ({totalScores > 0 ? Math.round((b.count / totalScores) * 100) : 0}%)
              </div>
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div className="flex gap-0.5 mt-1">
        {buckets.map((b, i) => (
          <div key={i} className="flex-1 text-center text-[10px] sm:text-[9px] text-gray-400 leading-none">
            {i % 2 === 0 ? b.lo : ""}
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="flex items-center justify-between mt-2 text-xs text-gray-400 border-t border-gray-100 pt-2">
        <span>{t("chart.score")}: 0-100</span>
        <span>{t("chart.mean")}: {meanScore} (n={totalScores})</span>
      </div>
    </div>
  );
}
