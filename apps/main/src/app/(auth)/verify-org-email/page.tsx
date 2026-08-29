"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { OrgAccessVerifyForm } from "@/components/org-access/OrgAccessVerifyForm";

export default function VerifyOrgEmailPage() {
  const t = useTranslations("orgAccess.verify");
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    async function loadToken() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      setToken(session.access_token);
    }
    loadToken();
  }, [router]);

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="text-center space-y-1">
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
        <p className="text-body-sm text-content-muted">{t("subheading")}</p>
      </div>

      {token && (
        <OrgAccessVerifyForm token={token} onSuccess={() => router.push("/")} />
      )}
    </div>
  );
}
