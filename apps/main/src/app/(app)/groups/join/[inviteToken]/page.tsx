"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { resolveInviteToken } from "@/lib/api/groups";
import { JoinGroupAction } from "@/components/groups/JoinGroupAction";
import { DomainVerifyForm } from "@/components/groups/DomainVerifyForm";
import type { DomainVerificationConfirmResponse, GroupDetail } from "@fe-el-seka/shared";

export default function JoinGroupPage() {
  const t = useTranslations("groups.join");
  const tGroups = useTranslations("groups");
  const router = useRouter();
  const params = useParams<{ inviteToken: string }>();
  const inviteToken = params.inviteToken;

  const [token, setToken] = useState<string | null>(null);
  const [group, setGroup] = useState<GroupDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          router.push(`/login?next=/groups/join/${inviteToken}`);
          return;
        }
        setToken(session.access_token);
        const detail = await resolveInviteToken(session.access_token, inviteToken);
        setGroup(detail);
      } catch (err) {
        const e = err as { error?: string; message?: string };
        setError(e?.error === "invite_link_invalid" ? t("inviteLinkInvalid") : e?.message ?? t("loadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [inviteToken, router, t]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !group || !token) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? t("loadFailed")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-4">
      <h1 className="text-h3 text-content-primary text-center">{t("title")}</h1>

      <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-body font-semibold text-content-primary">{group.name}</h2>
          {group.is_sponsored && (
            <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-dash-badge-bg text-dash-primary">
              {tGroups("sponsoredBadge")}
            </span>
          )}
        </div>
        {group.description && <p className="text-body-sm text-content-secondary">{group.description}</p>}
        <p className="text-caption text-content-muted">{tGroups("memberCount", { count: group.member_count })}</p>
      </div>

      {group.is_member ? (
        <div className="text-center space-y-3">
          <p className="text-body-sm text-content-secondary">{t("alreadyMember")}</p>
          <button
            type="button"
            onClick={() => router.push(`/groups/${group.id}`)}
            className="w-full bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
          >
            {t("viewGroup")}
          </button>
        </div>
      ) : group.is_sponsored ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
          <p className="text-body-sm text-content-secondary">{tGroups("sponsorship.eligibilityHint")}</p>
          <DomainVerifyForm
            token={token}
            groupId={group.id}
            onSuccess={(result: DomainVerificationConfirmResponse) => {
              setGroup({ ...group, ...result.group, is_member: true, is_domain_verified: true });
            }}
          />
        </div>
      ) : (
        <JoinGroupAction
          token={token}
          group={group}
          onJoined={(groupId) => router.push(`/groups/${groupId}`)}
        />
      )}
    </div>
  );
}
