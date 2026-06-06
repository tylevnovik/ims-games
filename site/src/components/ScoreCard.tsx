import { formatScore, getScoreBg } from "../lib/score";
import { useLang } from "../lib/i18n";

interface Props {
  label: string;
  score: number | null;
  tooltip?: string;
  isExternal?: boolean;
  isCustom?: boolean;
  highlight?: boolean;
}

export default function ScoreCard({ label, score, tooltip, isExternal, isCustom, highlight }: Props) {
  const [lang, , t] = useLang();
  const bg = score != null ? getScoreBg(score) : "bg-gray-50 border-gray-200";
  const display = score != null ? score.toFixed(1) : t("score.na");

  return (
    <div className={`rounded-xl border p-4 text-center ${bg} ${highlight ? "ring-2 ring-ims-400" : ""}`}>
      <div className="text-xs font-medium text-gray-500 mb-1 flex items-center justify-center gap-1">
        {label}
        {isExternal && <span title={t("tooltip.metacritic")} className="text-amber-500 cursor-help">&#9888;</span>}
        {tooltip && !isExternal && <span title={tooltip} className="text-gray-400 cursor-help">&#9432;</span>}
      </div>
      <div className={`text-2xl font-bold ${isCustom ? "text-ims-600" : "text-gray-800"}`}>{display}</div>
    </div>
  );
}
