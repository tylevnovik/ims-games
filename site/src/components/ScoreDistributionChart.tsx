import { useMemo } from "react";
import type { Review } from "../lib/types";

interface Props {
  reviews: Review[];
}

export default function ScoreDistributionChart({ reviews }: Props) {
  const buckets = useMemo(() => {
    const scores = reviews.filter((r) => r.score != null).map((r) => r.score!);
    if (!scores.length) return [];
    const bucketSize = 10;
    const counts: { range: string; count: number }[] = [];
    for (let i = 0; i < 100; i += bucketSize) {
      const lo = i;
      const hi = i + bucketSize;
      const count = scores.filter((s) => s >= lo && s < hi).length;
      counts.push({ range: `${lo}-${hi}`, count });
    }
    // Include 100
    counts[9].count += scores.filter((s) => s === 100).length;
    return counts;
  }, [reviews]);

  const maxCount = Math.max(...buckets.map((b) => b.count), 1);

  if (!buckets.length || buckets.every((b) => b.count === 0)) {
    return <p className="text-gray-500 text-sm text-center py-8">No score data to display.</p>;
  }

  const colors = [
    "bg-red-400", "bg-orange-400", "bg-orange-300", "bg-yellow-400",
    "bg-yellow-300", "bg-lime-400", "bg-green-400", "bg-emerald-400",
    "bg-emerald-500", "bg-green-600",
  ];

  return (
    <div className="flex items-end gap-1 h-32">
      {buckets.map((b, i) => (
        <div key={i} className="flex-1 flex flex-col items-center group relative">
          <div
            className={`w-full ${colors[i]} rounded-t transition-all`}
            style={{ height: `${(b.count / maxCount) * 100}%`, minHeight: b.count > 0 ? "4px" : "0" }}
          />
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
            {b.range}: {b.count}
          </div>
        </div>
      ))}
      <div className="text-xs text-gray-400 ml-1 self-end">Score</div>
    </div>
  );
}
