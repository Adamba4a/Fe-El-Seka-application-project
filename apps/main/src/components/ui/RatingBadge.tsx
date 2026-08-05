import { useTranslations } from "next-intl";

interface RatingBadgeProps {
  ratingAvg: number | null;
  ratingCount: number;
  className?: string;
}

export function RatingBadge({ ratingAvg, ratingCount, className = "" }: RatingBadgeProps) {
  const t = useTranslations("ratingBadge");
  if (ratingAvg === null || ratingCount === 0) {
    return <span className={`text-xs text-content-muted ${className}`}>{t("new")}</span>;
  }
  return (
    <span className={`inline-flex items-center gap-1 text-xs text-amber-600 font-medium ${className}`}>
      <span aria-hidden="true">★</span>
      {ratingAvg.toFixed(1)}
      <span className="text-content-muted font-normal">({ratingCount})</span>
    </span>
  );
}
