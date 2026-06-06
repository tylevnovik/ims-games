import { useState, useMemo } from "react";
import type { GameDetail, Review, CustomWeightConfig } from "../lib/types";
import { computeCustomScore, formatScore, getScoreBg } from "../lib/score";
import ScoreCard from "./ScoreCard";
import ReviewTable from "./ReviewTable";
import CustomWeightPanel from "./CustomWeightPanel";
import ScoreDistributionChart from "./ScoreDistributionChart";

interface Props {
  game: GameDetail;
}

export default function GameDetailClient({ game }: Props) {
  const [customConfig, setCustomConfig] = useState<CustomWeightConfig>({
    languageFilter: null,
    excludeVideoCreators: false,
    traditionalMediaOnly: false,
    platformFilter: null,
    excludeOutliers: false,
    reducedBigMedia: false,
    boostedIndieMedia: false,
    recentOnly: false,
    disabledSources: new Set(),
  });

  const customResult = useMemo(
    () => computeCustomScore(game.reviews || [], customConfig),
    [game.reviews, customConfig]
  );

  const mcBaseline = (game.external_baselines || []).find(
    (b) => b.source_platform === "metacritic"
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">{game.title}</h1>
        <div className="flex flex-wrap gap-3 mt-2 text-sm text-gray-500">
          {game.release_year && <span>{game.release_year}</span>}
          {game.developer && <span>&middot; {game.developer}</span>}
          {game.publisher && <span>&middot; {game.publisher}</span>}
        </div>
        <div className="flex flex-wrap gap-1 mt-2">
          {(game.genres || []).map((g) => (
            <span key={g} className="px-2 py-0.5 bg-ims-50 text-ims-700 text-xs rounded-full">{g}</span>
          ))}
          {(game.platforms || []).map((p) => (
            <span key={p} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">{p}</span>
          ))}
        </div>
      </div>

      {/* Score Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        <ScoreCard
          label="Metacritic"
          score={mcBaseline?.external_score ?? null}
          tooltip="External baseline score from Metacritic. Not an IMS algorithm score."
          isExternal
        />
        <ScoreCard
          label="IMS Raw"
          score={game.ims_raw}
          tooltip="Simple average of all valid normalized review scores."
        />
        <ScoreCard
          label="IMS Robust"
          score={game.ims_robust}
          tooltip="Trimmed mean: removes top/bottom 5% of scores. More resistant to outliers."
        />
        <ScoreCard
          label="IMS Calibrated"
          score={game.ims_calibrated}
          tooltip="Adjusted for each source's historical scoring tendency using z-score calibration."
        />
        <ScoreCard
          label="IMS Weighted"
          score={game.ims_weighted}
          tooltip="Weighted average using transparent source weights based on sample size, discrimination, and relevance."
          highlight
        />
        <ScoreCard
          label="Custom"
          score={customResult.count > 0 ? customResult.score : null}
          tooltip="Your customized score based on current filter settings."
          isCustom
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-bold text-gray-700 mb-3">Score Distribution</h3>
          <ScoreDistributionChart reviews={game.reviews || []} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-bold text-gray-700 mb-3">Language Distribution</h3>
          <div className="space-y-2">
            {Object.entries(game.language_distribution || {}).map(([lang, count]) => (
              <div key={lang} className="flex items-center gap-2 text-sm">
                <span className="w-8 font-medium text-gray-600">{lang}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div
                    className="bg-ims-400 h-full rounded-full"
                    style={{ width: `${Math.min(100, ((count as number) / (game.review_count || 1)) * 100)}%` }}
                  />
                </div>
                <span className="text-gray-500 w-10 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Custom Weight Panel */}
      <div className="mb-8">
        <CustomWeightPanel
          config={customConfig}
          onChange={setCustomConfig}
          result={customResult}
          languages={Object.keys(game.language_distribution || {})}
          platforms={game.platforms || []}
          sources={[...new Set((game.reviews || []).map((r) => r.source_name || "").filter(Boolean))]}
        />
      </div>

      {/* External Baselines */}
      {game.external_baselines && game.external_baselines.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8 text-sm">
          <p className="font-medium text-amber-800 mb-1">External Baseline Scores (not IMS algorithm)</p>
          {game.external_baselines.map((b) => (
            <p key={b.source_platform} className="text-amber-700">
              {b.source_platform}: <strong>{formatScore(b.external_score)}</strong>
              ({b.review_count} reviews) — <em>This score is from an external platform and does not represent IMS algorithm results.</em>
            </p>
          ))}
        </div>
      )}

      {/* Review Table */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          Reviews ({(game.reviews || []).length})
        </h2>
        <ReviewTable reviews={game.reviews || []} />
      </div>
    </div>
  );
}
