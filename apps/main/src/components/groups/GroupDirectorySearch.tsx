import { useState } from "react";
import { useTranslations } from "next-intl";
import type { SearchGroupsParams } from "@/lib/api/groups";

interface GroupDirectorySearchProps {
  onSearch: (params: SearchGroupsParams) => void;
}

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus transition-colors";

export function GroupDirectorySearch({ onSearch }: GroupDirectorySearchProps) {
  const t = useTranslations("groups");
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [routeTag, setRouteTag] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch({
      q: q.trim() || undefined,
      type: type || undefined,
      route_tag: routeTag.trim() || undefined,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-2">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("searchPlaceholder")}
        className={inputClass}
      />
      <div className="flex gap-2">
        <select value={type} onChange={(e) => setType(e.target.value)} className={inputClass}>
          <option value="">{t("type.all")}</option>
          <option value="general">{t("type.general")}</option>
          <option value="company">{t("type.company")}</option>
          <option value="university">{t("type.university")}</option>
        </select>
        <input
          type="text"
          value={routeTag}
          onChange={(e) => setRouteTag(e.target.value)}
          placeholder={t("routeTagPlaceholder")}
          className={inputClass}
        />
      </div>
      <button
        type="submit"
        className="w-full bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-2.5 font-medium transition-opacity"
      >
        {t("searchButton")}
      </button>
    </form>
  );
}
