import Link from "next/link";
import { useTranslations } from "next-intl";
import type { Group } from "@fe-el-seka/shared";

export function GroupCard({ group }: { group: Group }) {
  const t = useTranslations("groups");

  return (
    <Link
      href={`/groups/${group.id}`}
      className="block bg-surface-card rounded-xl p-4 border border-border-default hover:border-border-focus transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-base font-semibold text-content-primary truncate">{group.name}</p>
          {group.description && (
            <p className="text-body-sm text-content-muted line-clamp-2 mt-0.5">{group.description}</p>
          )}
        </div>
        <span className="shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-dash-badge-bg text-dash-primary">
          {t(`type.${group.type}`)}
        </span>
      </div>

      {group.route_tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {group.route_tags.map((tag) => (
            <span
              key={tag}
              className="text-caption px-2 py-0.5 rounded-full bg-surface-bg border border-border-default text-content-secondary"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <p className="text-caption text-content-muted mt-3">
        {t("memberCount", { count: group.member_count })}
      </p>
    </Link>
  );
}
