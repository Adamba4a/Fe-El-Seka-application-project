interface StatsCardProps {
  variant: "dark" | "light";
  label: string;
  value: string;
  subLabel?: string;
}

export function StatsCard({ variant, label, value, subLabel }: StatsCardProps) {
  const isDark = variant === "dark";
  return (
    <div
      className={`shrink-0 w-44 rounded-2xl p-4 ${
        isDark ? "bg-dash-primary text-white" : "bg-dash-surface text-dash-navy border border-dash-border"
      }`}
    >
      <p className={`text-[11px] font-semibold tracking-wide ${isDark ? "text-white/70" : "text-dash-text-muted"}`}>
        {label}
      </p>
      <p className="text-2xl font-bold mt-2">{value}</p>
      {subLabel && (
        <p className={`text-xs mt-1 ${isDark ? "text-white/80" : "text-dash-text-muted"}`}>{subLabel}</p>
      )}
    </div>
  );
}
