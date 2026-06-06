/**
 * IMS Games — i18n translation system
 *
 * Provides a flat key-value translation dictionary for zh/en,
 * a reactive language store, and helper utilities.
 */

import { useState, useEffect, useCallback } from "react";

export type Lang = "zh" | "en";

// ── Language store (reactive via custom events) ──

const STORAGE_KEY = "ims-lang";

export function getLang(): Lang {
  if (typeof window === "undefined") return "zh";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "zh") return stored;
  return "zh"; // default Chinese
}

export function setLang(lang: Lang) {
  localStorage.setItem(STORAGE_KEY, lang);
  window.dispatchEvent(new CustomEvent("ims-lang-change", { detail: lang }));
}

// ── Translations ──

const dict: Record<string, { zh: string; en: string }> = {
  // Nav
  "nav.games": { zh: "游戏库", en: "Games" },
  "nav.sources": { zh: "媒体源", en: "Sources" },
  "nav.methodology": { zh: "算法说明", en: "Methodology" },
  "nav.data_sources": { zh: "数据来源", en: "Data Sources" },
  "nav.goat": { zh: "GOAT", en: "GOAT" },
  "nav.goty": { zh: "GOTY", en: "GOTY" },

  // Home page
  "home.title_prefix": { zh: "IMS Games", en: "IMS Games" },
  "home.title_suffix": { zh: "— 透明的游戏评分", en: "— Transparent Game Scores" },
  "home.desc": {
    zh: "一个透明、可解释、可扩展的游戏评分聚合系统。不同于黑箱评分，IMS Games 的每一个分数都由公开的规则计算而来，你还可以自定义权重来匹配自己的偏好。",
    en: "A transparent, explainable, and extensible game score aggregation system. Unlike black-box scores, every IMS Games score is computed with publicly documented rules and you can customize the weighting to match your preferences.",
  },
  "home.stats.games": { zh: "收录游戏", en: "Games in Database" },
  "home.stats.sources": { zh: "媒体来源", en: "Media Sources" },
  "home.stats.reviews": { zh: "收录评论", en: "Reviews Collected" },
  "home.top_games": { zh: "评分最高游戏", en: "Top Rated Games" },
  "home.view_all": { zh: "查看全部 →", en: "View all →" },
  "home.methodology_title": { zh: "算法与方法论", en: "Algorithm & Methodology" },
  "home.methodology_desc": { zh: "了解 IMS Raw、Robust、Calibrated、Weighted 分数是如何计算的，每一条规则都公开透明。", en: "Learn how IMS Raw, Robust, Calibrated, and Weighted scores are calculated. Every rule is publicly documented." },
  "home.data_title": { zh: "数据来源与授权", en: "Data Sources & Licensing" },
  "home.data_desc": { zh: "了解我们的数据来源、收集方式，以及我们对归属和版权的处理方式。", en: "See where our data comes from, how it's collected, and our approach to attribution and licensing." },

  // Table headers (shared)
  "col.rank": { zh: "#", en: "#" },
  "col.game": { zh: "游戏", en: "Game" },
  "col.source": { zh: "来源", en: "Source" },
  "col.type": { zh: "类型", en: "Type" },
  "col.language": { zh: "语言", en: "Language" },
  "col.region": { zh: "地区", en: "Region" },
  "col.year": { zh: "年份", en: "Year" },
  "col.metacritic": { zh: "MC", en: "MC" },
  "col.ims_raw": { zh: "IMS 原始", en: "IMS Raw" },
  "col.ims_weighted": { zh: "IMS 加权", en: "IMS Weighted" },
  "col.reviews": { zh: "评论数", en: "Reviews" },
  "col.avg_score": { zh: "平均分", en: "Avg Score" },
  "col.weight": { zh: "权重", en: "Weight" },

  // Score labels
  "score.metacritic": { zh: "Metacritic", en: "Metacritic" },
  "score.raw": { zh: "IMS 原始", en: "IMS Raw" },
  "score.robust": { zh: "IMS 稳健", en: "IMS Robust" },
  "score.calibrated": { zh: "IMS 校准", en: "IMS Calibrated" },
  "score.weighted": { zh: "IMS 加权", en: "IMS Weighted" },
  "score.custom": { zh: "自定义", en: "Custom" },
  "score.na": { zh: "无", en: "N/A" },

  // Score tooltips
  "tooltip.metacritic": { zh: "Metacritic 外部基准分数，非 IMS 算法评分。", en: "External baseline score from Metacritic. Not an IMS algorithm score." },
  "tooltip.raw": { zh: "所有有效归一化评论分数的简单平均。", en: "Simple average of all valid normalized review scores." },
  "tooltip.robust": { zh: "截尾均值：去除最高/最低 5% 的分数，更抗异常值干扰。", en: "Trimmed mean: removes top/bottom 5% of scores. More resistant to outliers." },
  "tooltip.calibrated": { zh: "根据每个媒体的历史评分倾向进行 z-score 校准调整。", en: "Adjusted for each source's historical scoring tendency using z-score calibration." },
  "tooltip.weighted": { zh: "使用透明的媒体权重进行加权平均，权重基于样本量、区分度和相关性。", en: "Weighted average using transparent source weights based on sample size, discrimination, and relevance." },
  "tooltip.custom": { zh: "根据当前筛选设置计算出的自定义分数。", en: "Your customized score based on current filter settings." },

  // Game detail
  "game.score_distribution": { zh: "分数分布", en: "Score Distribution" },
  "game.lang_distribution": { zh: "语言分布", en: "Language Distribution" },
  "game.external_baselines": { zh: "外部基准分数（非 IMS 算法）", en: "External Baseline Scores (not IMS algorithm)" },
  "game.external_note": { zh: "此分数来自外部平台，不代表 IMS 算法结果。", en: "This score is from an external platform and does not represent IMS algorithm results." },
  "game.reviews_title": { zh: "评论", en: "Reviews" },
  "game.no_data": { zh: "暂无数据", en: "No data available" },
  "game.loading": { zh: "加载中...", en: "Loading..." },
  "game.load_error": { zh: "加载失败，请刷新页面重试。", en: "Failed to load. Please refresh the page." },

  // Review table
  "review.source": { zh: "来源", en: "Source" },
  "review.raw": { zh: "原始", en: "Raw" },
  "review.normalized": { zh: "归一化", en: "Normalized" },
  "review.weight": { zh: "权重", en: "Weight" },
  "review.date": { zh: "日期", en: "Date" },
  "review.lang": { zh: "语言", en: "Lang" },
  "review.summary": { zh: "摘要", en: "Summary" },
  "review.none": { zh: "暂无评论。", en: "No reviews available." },
  "review.search_source": { zh: "搜索媒体来源...", en: "Search source..." },
  "review.all_langs": { zh: "所有语言", en: "All Languages" },
  "review.all_platforms": { zh: "所有平台", en: "All Platforms" },
  "review.showing": { zh: "条评论", en: "reviews" },

  // Source detail
  "source.total_reviews": { zh: "总评论数", en: "Total Reviews" },
  "source.avg_score": { zh: "平均分", en: "Average Score" },
  "source.std_dev": { zh: "标准差", en: "Std Deviation" },
  "source.score_bias": { zh: "评分偏差", en: "Score Bias" },
  "source.weight_breakdown": { zh: "权重明细", en: "Weight Breakdown" },
  "source.recent_reviews": { zh: "近期评论", en: "Recent Reviews" },
  "source.genre_coverage": { zh: "类型覆盖", en: "Genre Coverage" },
  "source.platform_coverage": { zh: "平台覆盖", en: "Platform Coverage" },

  // Custom weight panel
  "custom.title": { zh: "自定义评分权重", en: "Customize Score Weights" },
  "custom.collapse": { zh: "▲ 收起", en: "▲ Collapse" },
  "custom.expand": { zh: "▼ 展开", en: "▼ Expand" },
  "custom.desc": { zh: "调整筛选条件，实时重新计算评分。", en: "Adjust filters to recalculate the score in real-time based on your preferences." },
  "custom.lang_filter": { zh: "语言筛选", en: "Language Filter" },
  "custom.all_langs": { zh: "所有语言", en: "All Languages" },
  "custom.platform_filter": { zh: "平台筛选", en: "Platform Filter" },
  "custom.all_platforms": { zh: "所有平台", en: "All Platforms" },
  "custom.exclude_outliers": { zh: "排除异常值", en: "Exclude outlier scores" },
  "custom.reduce_big": { zh: "降低大型媒体权重", en: "Reduce major media weight" },
  "custom.boost_indie": { zh: "提升独立媒体权重", en: "Boost indie media weight" },
  "custom.recent_only": { zh: "仅最近 30 天", en: "Last 30 days only" },
  "custom.toggle_sources": { zh: "切换个别媒体", en: "Toggle individual sources" },
  "custom.disabled": { zh: "已禁用", en: "disabled" },
  "custom.custom_score": { zh: "自定义评分：", en: "Custom Score: " },
  "custom.reviews_matched": { zh: "条评论匹配", en: "reviews matched" },

  // Distribution chart
  "chart.score": { zh: "分数", en: "Score" },
  "chart.mean": { zh: "均值", en: "Mean" },
  "chart.no_data": { zh: "暂无评分数据。", en: "No score data to display." },

  // Games list
  "games.title": { zh: "游戏库", en: "Game Library" },
  "games.search": { zh: "搜索游戏...", en: "Search games..." },
  "games.all_years": { zh: "所有年份", en: "All Years" },
  "games.all_genres": { zh: "所有类型", en: "All Genres" },
  "games.all_platforms": { zh: "所有平台", en: "All Platforms" },
  "games.sort_weighted": { zh: "排序：IMS 加权", en: "Sort: IMS Weighted" },
  "games.sort_raw": { zh: "排序：IMS 原始", en: "Sort: IMS Raw" },
  "games.sort_robust": { zh: "排序：IMS 稳健", en: "Sort: IMS Robust" },
  "games.sort_mc": { zh: "排序：Metacritic", en: "Sort: Metacritic" },
  "games.sort_count": { zh: "排序：评论数", en: "Sort: Review Count" },
  "games.sort_title": { zh: "排序：标题", en: "Sort: Title" },
  "games.found": { zh: "款游戏", en: "games found" },
  "games.prev": { zh: "上一页", en: "Prev" },
  "games.next": { zh: "下一页", en: "Next" },
  "games.page": { zh: "第 {0} / {1} 页", en: "Page {0} of {1}" },
  "games.desc": { zh: "↓ 降序", en: "↓ Desc" },
  "games.asc": { zh: "↑ 升序", en: "↑ Asc" },

  // Sources list
  "sources.title": { zh: "媒体源", en: "Media Sources" },
  "sources.desc": { zh: "IMS Games 收录的所有评论媒体及其历史表现指标。", en: "All review sources tracked by IMS Games, with historical performance metrics." },
  "sources.total": { zh: "个媒体源", en: "sources total" },

  // Methodology page
  "method.title": { zh: "算法与方法论", en: "Algorithm & Methodology" },
  "method.data_sources": { zh: "数据来源", en: "Data Sources" },
  "method.data_desc": { zh: "IMS Games 聚合来自多个透明来源的评论：", en: "IMS Games aggregates reviews from multiple transparent sources:" },
  "method.data_kaggle": { zh: "Metacritic Kaggle 数据集 — 12,000+ 款游戏的历史媒体评论分数", en: "Metacritic Kaggle Dataset — 12,000+ games with historical critic review scores" },
  "method.data_oc": { zh: "OpenCritic — API 或模拟数据，提供评论者信息和出处", en: "OpenCritic — API or mock data providing individual critic reviews with outlet info" },
  "method.data_future": { zh: "未来来源：Steam 评论、IGDB、中文游戏媒体、视频评论者", en: "Future sources: Steam reviews, IGDB, Chinese gaming media, video reviewers" },
  "method.normalization": { zh: "分数归一化", en: "Score Normalization" },
  "method.norm_desc": { zh: "所有分数都通过文档化的规则转换为统一的 0–100 量纲：", en: "All scores are converted to a uniform 0–100 scale using documented rules:" },
  "method.norm_note": { zh: "非数字评分（如\"推荐\"）不纳入数值平均。", en: "Non-numeric scores (e.g., \"Recommended\") are excluded from numeric averages." },
  "method.score_types": { zh: "分数类型", en: "Score Types" },
  "method.raw_title": { zh: "IMS 原始分数", en: "IMS Raw Score" },
  "method.raw_desc": { zh: "所有有效归一化评论分数的简单平均。mean(normalized_score)", en: "Simple average of all valid normalized review scores. mean(normalized_score)" },
  "method.median_title": { zh: "IMS 中位数分数", en: "IMS Median Score" },
  "method.median_desc": { zh: "所有归一化分数的中位数，对异常值不那么敏感。", en: "Median of all normalized scores. Less sensitive to outliers." },
  "method.robust_title": { zh: "IMS 稳健分数", en: "IMS Robust Score" },
  "method.robust_desc": { zh: "截尾均值：去除最高 5% 和最低 5% 后取平均（需 ≥20 条评论）。", en: "Trimmed mean: removes top 5% and bottom 5% of scores before averaging (requires ≥20 reviews)." },
  "method.calibrated_title": { zh: "IMS 校准分数", en: "IMS Calibrated Score" },
  "method.calibrated_desc": { zh: "针对每个媒体的历史评分倾向进行调整。总是打高分的媒体会被下调，严格的媒体会被上调。使用 z-score 校准：calibrated = global_mean + z × global_std", en: "Adjusts for each source's historical scoring tendency. A source that always scores high gets downward-adjusted; a strict source gets upward-adjusted. Uses z-score calibration: calibrated = global_mean + z × global_std" },
  "method.weighted_title": { zh: "IMS 加权分数", en: "IMS Weighted Score" },
  "method.weighted_desc": { zh: "使用透明的媒体权重进行加权平均。权重考虑样本量、区分度、类型/平台相关性和披露完整度。", en: "Weighted average using transparent source weights. Weights consider sample size, discrimination power, genre/platform relevance, and disclosure completeness." },
  "method.weight_formula": { zh: "媒体权重公式", en: "Media Weight Formula" },
  "method.weight_desc": { zh: "每个媒体的权重计算方式：", en: "Each source's weight is computed as:" },
  "method.weight_components": { zh: "组件", en: "Component" },
  "method.weight_range": { zh: "范围", en: "Range" },
  "method.weight_description": { zh: "说明", en: "Description" },
  "method.wc_base": { zh: "所有媒体的起始权重", en: "Starting weight for all sources" },
  "method.wc_sample": { zh: "历史评论越多，置信度越高", en: "More historical reviews = higher confidence" },
  "method.wc_disc": { zh: "评分方差越大的媒体权重越高", en: "Sources with more score variance get higher weight" },
  "method.wc_genre": { zh: "该游戏类型下的评论越多，相关性越高", en: "More reviews in the game's genre = higher relevance" },
  "method.wc_platform": { zh: "该游戏平台上的评论越多，相关性越高", en: "More reviews on the game's platform = higher relevance" },
  "method.wc_disclosure": { zh: "评论代码/赞助披露会略微提升权重", en: "Review code/sponsorship disclosure slightly boosts weight" },
  "method.baseline_title": { zh: "外部基准与 IMS 分数", en: "External Baseline vs IMS Scores" },
  "method.baseline_desc": { zh: "Metacritic 和 OpenCritic 分数仅作为外部基准展示，永远不会混入 IMS 算法分数。页面会清楚区分外部参考分数和 IMS 透明分数。", en: "Metacritic and OpenCritic scores are displayed as external baselines only. They are never mixed into IMS algorithm scores. The page clearly distinguishes between external reference scores and IMS transparent scores." },
  "method.limits_title": { zh: "已知限制 (v0.1)", en: "Known Limitations (v0.1)" },
  "method.limit1": { zh: "许多老游戏的类型和平台数据不完整", en: "Genre and platform data is incomplete for many older games" },
  "method.limit2": { zh: "字母等级转换使用固定映射", en: "Letter grade conversions use a fixed mapping" },
  "method.limit3": { zh: "校准要求每个媒体 ≥10 条评论", en: "Calibration requires ≥10 reviews per source" },
  "method.limit4": { zh: "权重组件使用简化公式；未来版本可能采用更复杂的模型", en: "Weight components use simplified formulas; future versions may use more sophisticated models" },
  "method.limit5": { zh: "视频创作者和中文媒体尚未纳入", en: "Video creators and Chinese media are not yet included" },

  // Data sources page
  "ds.title": { zh: "数据来源与授权", en: "Data Sources & Licensing" },
  "ds.kaggle_title": { zh: "Kaggle Metacritic 数据集", en: "Kaggle Metacritic Dataset" },
  "ds.kaggle_desc": { zh: "游戏元数据和媒体评论分数的主要数据来源。该开放数据集包含约 321,000 条评论，涵盖 12,000+ 款游戏和 500+ 家媒体。", en: "The primary data source for game metadata and critic review scores. This open dataset contains approximately 321,000 individual review entries across 12,000+ games from 500+ media outlets." },
  "ds.kaggle_contains": { zh: "包含：游戏标题、媒体名称、评论摘要、数字评分", en: "Contains: game titles, media outlet names, review text excerpts, numeric scores" },
  "ds.kaggle_not": { zh: "不包含：完整评论文章、评论者姓名、评论 URL", en: "Does NOT contain: full review articles, reviewer names, review URLs" },
  "ds.kaggle_source": { zh: "原始来源：Kaggle（公开可用数据集）", en: "Original source: Kaggle (publicly available dataset)" },
  "ds.kaggle_license": { zh: "许可：用于研究的公开数据集", en: "License: Public dataset for research use" },
  "ds.oc_title": { zh: "OpenCritic 数据", en: "OpenCritic Data" },
  "ds.oc_desc": { zh: "用于增强评论级数据，提供评论者信息、出处信息和评论链接。目前使用模拟数据进行演示。", en: "Used for enhanced review-level data with individual critic reviews, outlet information, reviewer names, and review links. Currently using mock data for demonstration." },
  "ds.oc_api": { zh: "API 集成计划在获取 API 密钥后进行", en: "API integration planned for when API key is available" },
  "ds.oc_mock": { zh: "为 25 款热门游戏使用模拟数据作为概念验证", en: "Mock data used for 25 popular games as proof-of-concept" },
  "ds.oc_url": { zh: "每条评论保留其出处 URL 用于归属", en: "Each review retains its provenance URL for attribution" },
  "ds.practices_title": { zh: "我们的数据实践", en: "Our Data Practices" },
  "ds.store": { zh: "我们存储什么：", en: "What we store:" },
  "ds.store_desc": { zh: "结构化字段（分数、日期、平台、语言）、短摘要和原始评论链接。", en: "Structured fields (scores, dates, platform, language), short summaries, and links to original reviews." },
  "ds.not_store": { zh: "我们不存储什么：", en: "What we don't store:" },
  "ds.not_store_desc": { zh: "完整的受版权保护的评论文本。仅存储结构化数据和简短摘录。", en: "Full copyrighted review text. Only structured data and brief excerpts." },
  "ds.attr": { zh: "归属：", en: "Attribution:" },
  "ds.attr_desc": { zh: "每条评论条目都保留出处 URL，链接到原始来源。原始评分归属于 respective 媒体。", en: "Every review entry retains a provenance URL linking to the original source. Original scores are credited to their respective outlets." },
  "ds.purpose": { zh: "用途：", en: "Purpose:" },
  "ds.purpose_desc": { zh: "本站仅用于研究、演示和评分聚合实验。", en: "This site is for research, demonstration, and score aggregation experiments only." },
  "ds.freshness": { zh: "数据时效：", en: "Data freshness:" },
  "ds.freshness_desc": { zh: "数据于 {0} 收集和处理。这是一个静态快照，不是实时更新。", en: "Data was collected and processed on {0}. This is a static snapshot, not a live feed." },
  "ds.copyright_title": { zh: "版权声明", en: "Copyright Notice" },
  "ds.copyright": { zh: "所有评论内容、分数和元数据均属于其各自所有者。IMS Games 仅存储结构化数据和简短摘录用于聚合目的。完整评论内容可在原始来源 URL 处获取。本项目与 Metacritic、OpenCritic 或任何游戏发行商无关。", en: "All review content, scores, and metadata belong to their respective owners. IMS Games only stores structured data and brief excerpts for aggregation purposes. Full review content is available at the original source URLs. This project is not affiliated with Metacritic, OpenCritic, or any game publisher." },

  // GOAT page
  "goat.page_title": { zh: "GOAT — 史上最伟大游戏", en: "GOAT — Greatest of All Time" },
  "goat.subtitle": { zh: "史上最伟大游戏", en: "Greatest of All Time" },
  "goat.page_desc": { zh: "基于 IMS 加权分数排名，选出数据库中最伟大的游戏。", en: "Ranked by IMS Weighted Score — the greatest games in our database." },
  "goat.title": { zh: "GOAT", en: "GOAT" },
  "goat.candidates": { zh: "候选排行", en: "Top Candidates" },
  "goat.based_on": { zh: "排名基于 IMS 加权分（ims_weighted），数据覆盖 12,000+ 款游戏。", en: "Ranked by IMS Weighted Score. Covers 12,000+ games." },
  "goat.no_data": { zh: "暂无评分数据。", en: "No score data available." },

  // GOTY page
  "goty.page_title": { zh: "GOTY — 年度游戏", en: "GOTY — Game of the Year" },
  "goty.subtitle": { zh: "年度游戏", en: "Game of the Year" },
  "goty.page_desc": { zh: "对比 The Game Awards、BAFTA、GDC 三大颁奖典礼的年度游戏得主，以及 IMS 评分的年度最佳。", en: "Compare Game of the Year winners from The Game Awards, BAFTA, and GDC with IMS score rankings." },
  "goty.select_year": { zh: "选择年份", en: "Select Year" },
  "goty.winner": { zh: "年度最佳", en: "GOTY Winner" },
  "goty.nominees": { zh: "提名", en: "Nominees" },
  "goty.consensus": { zh: "多奖共识 — 以下游戏获得多个年度最佳奖项：", en: "Consensus — These games won multiple GOTY awards:" },
  "goty.ims_top": { zh: "IMS 年度 Top 10", en: "IMS Top 10 of" },
  "goty.no_data": { zh: "暂无年度游戏数据。", en: "No GOTY data available." },
  "goty.no_ims_data": { zh: "该年份暂无 IMS 评分数据。", en: "No IMS score data for this year." },
  "goty.about": { zh: "颁奖数据来源于 The Game Awards (TGA)、英国学院游戏奖 (BAFTA)、游戏开发者选择奖 (GDC)。", en: "Award data sourced from The Game Awards (TGA), BAFTA Games Awards, and Game Developers Choice Awards (GDC)." },

  // Footer
  "footer.tagline": { zh: "IMS Games — 透明、可解释、可扩展的游戏评分聚合。", en: "IMS Games — Transparent, explainable, and extensible game score aggregation." },
  "footer.version": { zh: "算法 v0.1.0 · 所有分数均由公开文档化的规则计算。", en: "Algorithm v0.1.0 · All scores are computed with publicly documented rules." },
};

/**
 * Translate a key with optional interpolation.
 * Usage: t("games.page", [1, 5]) → "第 1 / 5 页"
 */
export function t(key: string, lang?: Lang, args?: (string | number)[]): string {
  const l = lang ?? getLang();
  const entry = dict[key];
  if (!entry) return key;
  let text = entry[l] || entry.en || key;
  if (args) {
    args.forEach((a, i) => {
      text = text.replace(`{${i}}`, String(a));
    });
  }
  return text;
}

/**
 * React hook for translations.
 * Re-renders component when language changes.
 */
export function useLang(): [Lang, () => string[], (key: string, args?: (string | number)[]) => string] {
  const [lang, setLangState] = useState<Lang>(getLang);

  useEffect(() => {
    const handler = (e: Event) => {
      setLangState((e as CustomEvent).detail as Lang);
    };
    window.addEventListener("ims-lang-change", handler);
    return () => window.removeEventListener("ims-lang-change", handler);
  }, []);

  const keys = useCallback(() => Object.keys(dict), []);

  const translate = useCallback(
    (key: string, args?: (string | number)[]) => t(key, lang, args),
    [lang]
  );

  return [lang, keys, translate];
}
