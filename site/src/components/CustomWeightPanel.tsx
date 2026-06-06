import { useState } from "react";
import type { CustomWeightConfig } from "../lib/types";
import { useLang } from "../lib/i18n";

interface Props {
  config: CustomWeightConfig;
  onChange: (config: CustomWeightConfig) => void;
  result: { score: number; count: number };
  languages: string[];
  platforms: string[];
  sources: string[];
}

export default function CustomWeightPanel({ config, onChange, result, languages, platforms, sources }: Props) {
  const [lang, , t] = useLang();
  const [open, setOpen] = useState(false);

  const toggle = (key: keyof CustomWeightConfig, value?: any) => {
    const next = { ...config };
    if (key === "disabledSources") return;
    (next as any)[key] = value ?? !(next as any)[key];
    onChange(next);
  };

  const toggleSource = (name: string) => {
    const next = new Set(config.disabledSources);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    onChange({ ...config, disabledSources: next });
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200">
      <button onClick={() => setOpen(!open)} className="w-full px-4 py-3 flex items-center justify-between text-left">
        <span className="font-bold text-gray-800">{t("custom.title")}</span>
        <span className="text-gray-400 text-sm">{open ? t("custom.collapse") : t("custom.expand")}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3 space-y-4">
          <p className="text-xs text-gray-500">{t("custom.desc")}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">{t("custom.lang_filter")}</label>
              <select value={config.languageFilter || ""} onChange={(e) => toggle("languageFilter", e.target.value || null)} className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm bg-white">
                <option value="">{t("custom.all_langs")}</option>
                {languages.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">{t("custom.platform_filter")}</label>
              <select value={config.platformFilter || ""} onChange={(e) => toggle("platformFilter", e.target.value || null)} className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm bg-white">
                <option value="">{t("custom.all_platforms")}</option>
                {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={config.excludeOutliers} onChange={() => toggle("excludeOutliers")} className="rounded" />
              {t("custom.exclude_outliers")}
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={config.reducedBigMedia} onChange={() => toggle("reducedBigMedia")} className="rounded" />
              {t("custom.reduce_big")}
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={config.boostedIndieMedia} onChange={() => toggle("boostedIndieMedia")} className="rounded" />
              {t("custom.boost_indie")}
            </label>
          </div>

          {sources.length > 0 && sources.length <= 30 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-ims-600 font-medium">
                {t("custom.toggle_sources")} ({config.disabledSources.size} {t("custom.disabled")})
              </summary>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-1 mt-2 max-h-48 overflow-y-auto">
                {sources.map((s) => (
                  <label key={s} className="flex items-center gap-1.5 cursor-pointer text-gray-600">
                    <input type="checkbox" checked={!config.disabledSources.has(s)} onChange={() => toggleSource(s)} className="rounded" />
                    <span className="truncate">{s}</span>
                  </label>
                ))}
              </div>
            </details>
          )}

          <div className="bg-ims-50 border border-ims-200 rounded-lg p-3 flex items-center justify-between">
            <div>
              <span className="text-sm text-gray-600">{t("custom.custom_score")}</span>
              <span className="text-xl font-bold text-ims-700">{result.count > 0 ? result.score.toFixed(1) : t("score.na")}</span>
            </div>
            <span className="text-sm text-gray-500">{result.count} {t("custom.reviews_matched")}</span>
          </div>
        </div>
      )}
    </div>
  );
}
