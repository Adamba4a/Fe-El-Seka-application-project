"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { searchGroups, type SearchGroupsParams } from "@/lib/api/groups";
import { GroupDirectorySearch } from "@/components/groups/GroupDirectorySearch";
import { GroupCard } from "@/components/groups/GroupCard";
import type { Group } from "@fe-el-seka/shared";

export default function GroupsDirectoryPage() {
  const t = useTranslations("groups");
  const router = useRouter();
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(
    async (params: SearchGroupsParams) => {
      setLoading(true);
      setError(null);
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }
        const res = await searchGroups(session.access_token, params);
        setGroups(res.items);
      } catch {
        setError(t("loadFailed"));
      } finally {
        setLoading(false);
      }
    },
    [router, t]
  );

  useEffect(() => {
    runSearch({});
  }, [runSearch]);

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-h3 text-content-primary">{t("directoryHeading")}</h1>
        <Link href="/groups/create" className="text-body-sm text-brand-primary font-medium">
          {t("createLink")}
        </Link>
      </div>

      <GroupDirectorySearch onSearch={runSearch} />

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      ) : error ? (
        <p className="text-body-sm text-content-destructive text-center py-8">{error}</p>
      ) : groups.length === 0 ? (
        <p className="text-body-sm text-content-muted text-center py-8">{t("noGroupsFound")}</p>
      ) : (
        <div className="space-y-3">
          {groups.map((g) => (
            <GroupCard key={g.id} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}
