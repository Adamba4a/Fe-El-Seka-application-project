"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { createGroup } from "@/lib/api/groups";
import { DomainVerifyForm } from "@/components/groups/DomainVerifyForm";
import type { DomainGroupType, DomainVerificationConfirmResponse, GroupType } from "@fe-el-seka/shared";

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus transition-colors";

export default function CreateGroupPage() {
  const t = useTranslations("groups");
  const router = useRouter();
  const [type, setType] = useState<GroupType>("general");
  const [token, setToken] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [routeTags, setRouteTags] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadToken() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      setToken(session.access_token);
    }
    loadToken();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      const group = await createGroup(session.access_token, {
        name: name.trim(),
        description: description.trim() || undefined,
        route_tags: routeTags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
      router.push(`/groups/${group.id}`);
    } catch (err: any) {
      setError(err?.message ?? t("createFailed"));
    } finally {
      setLoading(false);
    }
  };

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
        <h1 className="text-h3 text-content-primary">{t("createHeading")}</h1>
      </div>

      <div className="space-y-1">
        <label className="block text-label text-content-secondary">{t("groupTypeLabel")}</label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as GroupType)}
          className={inputClass}
        >
          <option value="general">{t("type.general")}</option>
          <option value="company">{t("type.company")}</option>
          <option value="university">{t("type.university")}</option>
        </select>
      </div>

      {type !== "general" ? (
        <div className="space-y-3">
          <p className="text-caption text-content-muted">{t("groupTypeHint")}</p>
          {token && (
            <DomainVerifyForm
              token={token}
              requestedGroupType={type as DomainGroupType}
              onSuccess={(result: DomainVerificationConfirmResponse) => router.push(`/groups/${result.group.id}`)}
            />
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="block text-label text-content-secondary">{t("nameLabel")}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
              className={inputClass}
            />
          </div>

          <div className="space-y-1">
            <label className="block text-label text-content-secondary">{t("descriptionLabel")}</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              maxLength={500}
              className={`${inputClass} resize-none`}
            />
          </div>

          <div className="space-y-1">
            <label className="block text-label text-content-secondary">{t("routeTagsLabel")}</label>
            <input
              type="text"
              value={routeTags}
              onChange={(e) => setRouteTags(e.target.value)}
              placeholder={t("routeTagsPlaceholder")}
              className={inputClass}
            />
            <p className="text-caption text-content-muted">{t("routeTagsHint")}</p>
          </div>

          {error && <p className="text-body-sm text-content-destructive">{error}</p>}

          <button
            type="submit"
            disabled={loading || !name.trim()}
            className="w-full bg-dash-primary hover:opacity-90 disabled:opacity-50 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
          >
            {loading ? t("creating") : t("createButton")}
          </button>
        </form>
      )}
    </div>
  );
}
