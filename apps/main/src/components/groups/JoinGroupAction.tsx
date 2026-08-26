"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { DomainVerifyForm } from "@/components/groups/DomainVerifyForm";
import { joinGroup } from "@/lib/api/groups";
import type { DomainGroupType, DomainVerificationConfirmResponse, GroupDetail } from "@fe-el-seka/shared";

interface JoinGroupActionProps {
  token: string;
  group: GroupDetail;
  onJoined: (groupId: string) => void;
}

export function JoinGroupAction({ token, group, onJoined }: JoinGroupActionProps) {
  const t = useTranslations("groups.join");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (group.type !== "general") {
    return (
      <div className="space-y-3">
        <p className="text-body-sm text-content-secondary">{t("domainVerifiedRequired")}</p>
        <DomainVerifyForm
          token={token}
          requestedGroupType={group.type as DomainGroupType}
          onSuccess={(result: DomainVerificationConfirmResponse) => onJoined(result.group.id)}
        />
      </div>
    );
  }

  const handleJoin = async () => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      await joinGroup(token, group.id);
      onJoined(group.id);
    } catch (err) {
      const e = err as { message?: string };
      setError(e?.message ?? t("joinFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      {error && <p className="text-body-sm text-content-destructive">{error}</p>}
      <button
        type="button"
        onClick={handleJoin}
        disabled={loading}
        className="w-full bg-dash-primary hover:opacity-90 disabled:opacity-50 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
      >
        {loading ? t("joining") : t("joinButton")}
      </button>
    </div>
  );
}
