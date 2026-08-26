"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";
import { getGroup, getGroupRides } from "@/lib/api/groups";
import { JoinGroupAction } from "@/components/groups/JoinGroupAction";
import { InviteLinkShare } from "@/components/groups/InviteLinkShare";
import { MemberList } from "@/components/groups/MemberList";
import { RideCard } from "@/components/rides/RideCard";
import type { GroupDetail, Ride } from "@fe-el-seka/shared";

export default function GroupDetailPage() {
  const t = useTranslations("groups");
  const router = useRouter();
  const params = useParams<{ groupId: string }>();
  const groupId = params.groupId;

  const [token, setToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [group, setGroup] = useState<GroupDetail | null>(null);
  const [rides, setRides] = useState<Ride[]>([]);
  const [loading, setLoading] = useState(true);
  const [ridesLoading, setRidesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push("/login"); return; }
        setToken(session.access_token);
        setUserId(session.user.id);
        const detail = await getGroup(session.access_token, groupId);
        setGroup(detail);

        if (detail.is_member) {
          setRidesLoading(true);
          try {
            const res = await getGroupRides(session.access_token, groupId);
            setRides(res.rides);
          } finally {
            setRidesLoading(false);
          }
        }
      } catch (err: any) {
        setError(err?.message ?? t("loadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [groupId, router, t]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !group) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? t("loadFailed")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-h3 text-content-primary truncate">{group.name}</h1>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-dash-badge-bg text-dash-primary">
            {t(`type.${group.type}`)}
          </span>
          <span className="text-caption text-content-muted">
            {t("memberCount", { count: group.member_count })}
          </span>
        </div>

        {group.description && <p className="text-body-sm text-content-secondary">{group.description}</p>}

        {group.route_tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
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
      </div>

      {group.is_owner && token && <InviteLinkShare token={token} groupId={group.id} />}

      {group.is_member && token && userId && (
        <MemberList
          token={token}
          groupId={group.id}
          currentUserId={userId}
          isOwner={group.is_owner}
          onLeft={() => router.push("/groups")}
          onArchived={() => router.push("/groups")}
        />
      )}

      {group.is_member ? (
        <div className="space-y-3">
          <h2 className="text-label text-content-secondary">{t("activeRidesHeading")}</h2>
          {ridesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Spinner />
            </div>
          ) : rides.length === 0 ? (
            <p className="text-body-sm text-content-muted text-center py-8">{t("noActiveRides")}</p>
          ) : (
            <div className="space-y-3">
              {rides.map((ride) => (
                <RideCard key={ride.id} ride={ride} href={`/rides/${ride.id}`} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-body-sm text-content-muted text-center py-2">{t("joinToSeeRides")}</p>
          {token && (
            <JoinGroupAction
              token={token}
              group={group}
              onJoined={(joinedGroupId) => {
                if (joinedGroupId === group.id) {
                  window.location.reload();
                } else {
                  router.push(`/groups/${joinedGroupId}`);
                }
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}
