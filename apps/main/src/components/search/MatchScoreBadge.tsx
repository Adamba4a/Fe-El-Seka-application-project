interface MatchScoreBadgeProps {
  score_pct: number | null
}

export function MatchScoreBadge({ score_pct }: MatchScoreBadgeProps) {
  if (score_pct === null) return null

  const colourClass =
    score_pct >= 70
      ? "bg-green-100 text-green-800"
      : score_pct >= 40
      ? "bg-amber-100 text-amber-800"
      : "bg-gray-100 text-gray-600"

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colourClass}`}
    >
      {score_pct}% match
    </span>
  )
}
