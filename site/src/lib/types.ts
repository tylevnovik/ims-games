export interface GameSummary {
  game_id: string;
  title: string;
  release_year: number | null;
  developer: string | null;
  publisher: string | null;
  genres: string[];
  platforms: string[];
  description: string | null;
  metacritic_score: number | null;
  rawg_metacritic_score: number | null;
  ims_raw: number | null;
  ims_robust: number | null;
  ims_calibrated: number | null;
  ims_weighted: number | null;
  review_count: number;
  has_enhanced_data: boolean;
}

export interface Review {
  source_name: string | null;
  reviewer: string | null;
  score: number | null;
  raw_score: number | null;
  weight: number | null;
  weight_explanation: string | null;
  url: string | null;
  date: string | null;
  language: string | null;
  platform: string | null;
  summary: string | null;
  positive_points: string | null;
  negative_points: string | null;
}

export interface GameDetail extends GameSummary {
  reviews: Review[];
  source_metrics?: Record<string, SourceMetric>;
  external_baselines: ExternalBaseline[];
  language_distribution: Record<string, number>;
  platform_distribution: Record<string, number>;
}

export interface SourceMetric {
  sample_count?: number;
  mean_score?: number;
  score_std?: number;
  score_bias?: number;
  discrimination_power?: number;
  genre_coverage?: Record<string, number> | unknown;
  platform_coverage?: Record<string, number> | unknown;
}

export interface ExternalBaseline {
  source_platform: string;
  external_score: number | null;
  external_user_score: number | null;
  review_count: number | null;
  source_url: string | null;
  data_source: string | null;
}

export interface SourceSummary {
  source_id: string;
  name: string;
  source_type: string | null;
  language: string | null;
  country_region: string | null;
  review_count: number;
  mean_score: number | null;
  base_weight: number | null;
}

export interface SourceDetail extends SourceSummary {
  metrics: Record<string, unknown>;
  weights: { records: WeightRecord[] } | Record<string, never>;
  recent_reviews: { game_title: string; game_id: string; score: number | null; url: string | null; date: string | null }[];
  genre_coverage: Record<string, number>;
  platform_coverage: Record<string, number>;
}

export interface WeightRecord {
  genre: string | null;
  platform: string | null;
  base_weight?: number;
  context_weight?: number;
  confidence?: number;
  explanation?: string;
}

export interface SiteMeta {
  algorithm_version: string;
  build_timestamp: string;
  total_games: number;
  total_sources: number;
  total_reviews: number;
  data_sources: { name: string; type: string }[];
}

export interface CustomWeightConfig {
  languageFilter: string | null;
  platformFilter: string | null;
  excludeOutliers: boolean;
  reducedBigMedia: boolean;
  boostedIndieMedia: boolean;
  disabledSources: Set<string>;
}
