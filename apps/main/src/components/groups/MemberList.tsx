"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import {
  archiveGroup,
  getGroupMembers,
  leaveGroup,
  removeMember,
  transferOwnership,
} from "@/lib/api/groups";
import type { GroupMember } from "@fe-el-seka/shared";

interface MemberListProps {
  token: string;
  groupId: string;
  currentUserId: string;
  isOwner: boolean;
  onLeft: () => void;
  onArchived: () => void;
}

type PendingAction =
  | { kind: "leave" }
  | { kind: "remove"; userId: string }
  | { kind: "transfer"; userId: string }
  | { kind: "archive" };

const KNOWN_ERROR_CODES = new Set([
  "ownership_transfer_required",
  "not_group_owner",
  "cannot_remove_owner",
  "already_owner",
  "not_a_group_member",
  "group_archived",
  "group_not_found",
  "invalid_user_id",
]);

function errorMessage(
  e: { error?: string; message?: string },
  t: (key: string) => string
): string {
  if (e?.error && KNOWN_ERROR_CODES.has(e.error)) {
    return t(`errors.${e.error}`);
  }
  return e?.message ?? t("actionFailed");
}

export function MemberList({ token, groupId, currentUserId, isOwner, onLeft, onArchived }: MemberListProps) {
  const t = useTranslations("groups.members");
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<PendingAction | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        const res = await getGroupMembers(token, groupId);
        setMembers(res);
      } catch (err) {
        const e = err as { message?: string };
        setError(e?.message ?? t("loadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [token, groupId, t]);

  const runAction = async (action: PendingAction) => {
    setBusy(true);
    setError("");
    try {
      if (action.kind === "leave") {
        await leaveGroup(token, groupId);
        onLeft();
        return;
      }
      if (action.kind === "remove") {
        await removeMember(token, groupId, action.userId);
        setMembers((prev) => prev.filter((m) => m.user_id !== action.userId));
      } else if (action.kind === "transfer") {
        await transferOwnership(token, groupId, { new_owner_user_id: action.userId });
        window.location.reload();
        return;
      } else if (action.kind === "archive") {
        await archiveGroup(token, groupId);
        onArchived();
        return;
      }
    } catch (err) {
      const e = err as { error?: string; message?: string };
      setError(errorMessage(e, t));
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
      <h2 className="text-label text-content-secondary">{t("heading")}</h2>

      <div className="space-y-2">
        {members.map((member) => {
          const isSelf = member.user_id === currentUserId;
          return (
            <div key={member.id} className="flex items-center justify-between gap-2 py-1.5">
              <div className="min-w-0 flex items-center gap-2">
                <span className="text-body-sm text-content-primary truncate">
                  {member.display_name}
                  {isSelf && <span className="text-content-muted"> {t("you")}</span>}
                </span>
                {member.role === "owner" && (
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-dash-badge-bg text-dash-primary shrink-0">
                    {t("ownerBadge")}
                  </span>
                )}
              </div>

              {isOwner && !isSelf && (
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setConfirming({ kind: "transfer", userId: member.user_id })}
                    className="text-caption font-medium text-dash-primary hover:opacity-80 disabled:opacity-50"
                  >
                    {t("transferButton")}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setConfirming({ kind: "remove", userId: member.user_id })}
                    className="text-caption font-medium text-content-destructive hover:opacity-80 disabled:opacity-50"
                  >
                    {t("removeButton")}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error && <p className="text-body-sm text-content-destructive">{error}</p>}

      {confirming && (
        <ConfirmBar
          text={t(`${confirming.kind}Confirm`)}
          confirmLabel={t("confirmButton")}
          cancelLabel={t("cancelButton")}
          busy={busy}
          onConfirm={() => runAction(confirming)}
          onCancel={() => setConfirming(null)}
        />
      )}

      {!confirming && (
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirming({ kind: "leave" })}
            className="flex-1 border border-border-default rounded-xl py-2 text-body-sm font-medium text-content-secondary hover:border-border-focus disabled:opacity-50 transition-colors"
          >
            {t("leaveButton")}
          </button>
          {isOwner && (
            <button
              type="button"
              disabled={busy}
              onClick={() => setConfirming({ kind: "archive" })}
              className="flex-1 border border-border-default rounded-xl py-2 text-body-sm font-medium text-content-destructive hover:border-border-focus disabled:opacity-50 transition-colors"
            >
              {t("archiveButton")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ConfirmBar({
  text,
  confirmLabel,
  cancelLabel,
  busy,
  onConfirm,
  onCancel,
}: {
  text: string;
  confirmLabel: string;
  cancelLabel: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-lg bg-surface-bg border border-border-default p-3 space-y-2">
      <p className="text-body-sm text-content-secondary">{text}</p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onConfirm}
          className="flex-1 bg-dash-primary hover:opacity-90 disabled:opacity-50 text-content-inverse rounded-xl py-2 text-body-sm font-medium transition-opacity"
        >
          {busy ? "…" : confirmLabel}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="flex-1 border border-border-default rounded-xl py-2 text-body-sm font-medium text-content-secondary hover:border-border-focus disabled:opacity-50 transition-colors"
        >
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}
