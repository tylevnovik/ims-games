import type { GameSummary } from "./types";

export const MIN_RANKING_REVIEWS = 75;

export function isRankingEligible(game: Pick<GameSummary, "ims_weighted" | "review_count">): boolean {
  return game.ims_weighted != null && (game.review_count ?? 0) >= MIN_RANKING_REVIEWS;
}
