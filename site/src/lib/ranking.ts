import type { GameSummary } from "./types";

export const MIN_RANKING_REVIEWS = 75;

export type ImsSortField = "ims_weighted" | "ims_raw" | "ims_robust" | "ims_calibrated";

export const IMS_SORT_FIELDS = new Set<ImsSortField>([
  "ims_weighted",
  "ims_raw",
  "ims_robust",
  "ims_calibrated",
]);

export function isImsSortField(field: string): field is ImsSortField {
  return IMS_SORT_FIELDS.has(field as ImsSortField);
}

export function isRankingEligible(game: Pick<GameSummary, "ims_weighted" | "review_count">): boolean {
  return game.ims_weighted != null && (game.review_count ?? 0) >= MIN_RANKING_REVIEWS;
}

/** Sort IMS score columns with ranking-eligible games first. */
export function compareImsSort(
  a: GameSummary,
  b: GameSummary,
  field: ImsSortField,
  dir: "asc" | "desc",
): number {
  const aEligible = isRankingEligible(a);
  const bEligible = isRankingEligible(b);
  if (aEligible !== bEligible) {
    return aEligible ? -1 : 1;
  }
  const va = a[field] ?? -1;
  const vb = b[field] ?? -1;

  if (!aEligible && !bEligible) {
    const aCount = a.review_count ?? 0;
    const bCount = b.review_count ?? 0;
    if (aCount !== bCount) {
      return dir === "desc" ? bCount - aCount : aCount - bCount;
    }
  }

  return dir === "desc" ? vb - va : va - vb;
}
