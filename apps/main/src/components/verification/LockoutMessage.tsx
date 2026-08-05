import { useTranslations } from "next-intl";

interface LockoutMessageProps {
  lockoutMessage: string;
  supportEmail?: string;
}

export function LockoutMessage({ lockoutMessage, supportEmail }: LockoutMessageProps) {
  const t = useTranslations("onboarding.lockout");
  const email = supportEmail ?? lockoutMessage.match(/[\w.+-]+@[\w-]+\.[\w.]+/)?.[0];

  return (
    <div className="bg-status-in-progress-bg border border-status-in-progress rounded-xl p-4 space-y-2">
      <p className="text-label text-status-in-progress">{t("title")}</p>
      <p className="text-body-sm text-content-secondary">{lockoutMessage}</p>
      {email && (
        <a
          href={`mailto:${email}`}
          className="inline-block text-body-sm text-brand-primary underline font-medium"
        >
          {t("contactPrefix")} {email}
        </a>
      )}
    </div>
  );
}
