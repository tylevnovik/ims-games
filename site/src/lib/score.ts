import type { Review, CustomWeightConfig } from "./types";

export function computeCustomScore(
  reviews: Review[],
  config: CustomWeightConfig
): { score: number; count: number } {
  let filtered = reviews.filter((r) => r.score != null);

  if (config.languageFilter) {
    filtered = filtered.filter((r) => r.language === config.languageFilter);
  }
  if (config.excludeVideoCreators) {
    // v0.1: no source_type on review level, skip for now
  }
  if (config.platformFilter) {
    filtered = filtered.filter((r) => r.platform === config.platformFilter);
  }
  if (config.disabledSources.size > 0) {
    filtered = filtered.filter((r) => !config.disabledSources.has(r.source_name || ""));
  }
  if (config.excludeOutliers && filtered.length >= 4) {
    const scores = filtered.map((r) => r.score!).sort((a, b) => a - b);
    const q1 = scores[Math.floor(scores.length * 0.25)];
    const q3 = scores[Math.floor(scores.length * 0.75)];
    const iqr = q3 - q1;
    const lo = q1 - 1.5 * iqr;
    const hi = q3 + 1.5 * iqr;
    filtered = filtered.filter((r) => r.score! >= lo && r.score! <= hi);
  }

  if (filtered.length === 0) return { score: 0, count: 0 };

  let weights = filtered.map((r) => {
    let w = r.weight || 1.0;
    if (config.reducedBigMedia) w *= 0.8;
    if (config.boostedIndieMedia) w *= 1.1;
    return w;
  });

  const wSum = filtered.reduce((acc, r, i) => acc + r.score! * weights[i], 0);
  const wTotal = weights.reduce((a, b) => a + b, 0);

  return {
    score: wTotal > 0 ? Math.round((wSum / wTotal) * 10) / 10 : 0,
    count: filtered.length,
  };
}

export function getScoreColor(score: number): string {
  if (score >= 90) return "text-green-600";
  if (score >= 75) return "text-emerald-500";
  if (score >= 60) return "text-yellow-600";
  if (score >= 40) return "text-orange-500";
  return "text-red-500";
}

export function getScoreBg(score: number): string {
  if (score >= 90) return "bg-green-100 border-green-300";
  if (score >= 75) return "bg-emerald-50 border-emerald-200";
  if (score >= 60) return "bg-yellow-50 border-yellow-200";
  if (score >= 40) return "bg-orange-50 border-orange-200";
  return "bg-red-50 border-red-200";
}

export function formatScore(score: number | null | undefined): string {
  if (score == null) return "N/A";
  return score.toFixed(1);
}
