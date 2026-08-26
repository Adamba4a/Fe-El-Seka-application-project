"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { getInviteLink } from "@/lib/api/groups";

interface InviteLinkShareProps {
  token: string;
  groupId: string;
}

export function InviteLinkShare({ token, groupId }: InviteLinkShareProps) {
  const t = useTranslations("groups.inviteLink");
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const fetchLink = async () => {
    if (loading) return;
    setLoading(true);
    setError("");
    setCopied(false);
    try {
      const res = await getInviteLink(token, groupId);
      setInviteUrl(res.invite_url);
    } catch (err) {
      const e = err as { message?: string };
      setError(e?.message ?? t("loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable — the URL is still shown as selectable text.
    }
  };

  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-4 space-y-3">
      <h2 className="text-label text-content-secondary">{t("heading")}</h2>

      {inviteUrl ? (
        <div className="space-y-2">
          <p className="text-body-sm text-content-secondary break-all bg-surface-bg rounded-lg px-3 py-2">
            {inviteUrl}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="flex-1 border border-border-default rounded-xl py-2 text-body-sm font-medium text-content-secondary hover:border-border-focus transition-colors"
            >
              {copied ? t("copied") : t("copyLink")}
            </button>
            <button
              type="button"
              onClick={fetchLink}
              disabled={loading}
              className="flex-1 border border-border-default rounded-xl py-2 text-body-sm font-medium text-content-secondary hover:border-border-focus disabled:opacity-50 transition-colors"
            >
              {loading ? t("regenerating") : t("regenerate")}
            </button>
          </div>
          <p className="text-caption text-content-muted">{t("regenerateHint")}</p>
        </div>
      ) : (
        <button
          type="button"
          onClick={fetchLink}
          disabled={loading}
          className="w-full border border-border-default rounded-xl py-2 text-body-sm font-medium text-content-secondary hover:border-border-focus disabled:opacity-50 transition-colors"
        >
          {loading ? t("generating") : t("getLink")}
        </button>
      )}

      {error && <p className="text-body-sm text-content-destructive">{error}</p>}
    </div>
  );
}
