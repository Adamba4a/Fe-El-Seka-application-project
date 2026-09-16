"use client";

import { useRef, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { LanguageToggle } from "@/components/layout/LanguageToggle";

export function SupportWidget() {
  const t = useTranslations("support");
  const locale = useLocale();
  const dialog = useRef<HTMLDialogElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const requestId = useRef<string | null>(null);
  const submitting = useRef(false);
  const [email, setEmail] = useState("");
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  function close() {
    dialog.current?.close();
    launcher.current?.focus();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const address = email.trim();
    const problem = description.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address) || address.length > 254) {
      setError(t("invalidEmail"));
      return;
    }
    if (problem.length < 10 || problem.length > 5000) {
      setError(t("invalidDescription"));
      return;
    }
    submitting.current = true;
    setPending(true);
    setError("");
    requestId.current ??= crypto.randomUUID();
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/support`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: requestId.current, email: address, description: problem, locale, website }),
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) {
        setError(t(response.status === 429 ? "rateLimited" : response.status === 422 ? "invalidForm" : "failed"));
        return;
      }
      setSent(true);
      setEmail("");
      setDescription("");
      requestId.current = null;
    } catch {
      setError(t("failed"));
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return (
    <>
      <button ref={launcher} type="button" onClick={() => { setSent(false); dialog.current?.showModal(); }}
        className="fixed z-40 rounded-full bg-brand-primary px-4 py-3 text-sm font-semibold text-white shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        style={{ insetInlineEnd: "1rem", bottom: "calc(5.5rem + env(safe-area-inset-bottom))" }}>
        {t("trigger")}
      </button>
      <dialog ref={dialog} aria-labelledby="support-title" onClose={() => launcher.current?.focus()}
        className="m-auto max-h-[85dvh] w-[calc(100%_-_2rem)] max-w-md overflow-y-auto rounded-2xl bg-white p-6 text-start text-gray-900 shadow-xl backdrop:bg-black/50">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 id="support-title" className="text-xl font-semibold">{t("title")}</h2>
          <LanguageToggle />
          <button type="button" onClick={close} aria-label={t("close")} className="min-h-11 min-w-11 rounded-lg border text-xl">×</button>
        </div>
        {sent ? (
          <div role="status" className="space-y-4">
            <p>{t("success")}</p>
            <button type="button" onClick={close} className="rounded-lg bg-brand-primary px-4 py-3 text-white">{t("close")}</button>
          </div>
        ) : (
          <form onSubmit={submit} noValidate className="space-y-4">
            <p className="text-sm text-gray-600">{t("intro")}</p>
            <div>
              <label htmlFor="support-email" className="mb-1 block font-medium">{t("email")}</label>
              <input id="support-email" type="email" autoComplete="email" dir="ltr" required maxLength={254}
                disabled={pending} value={email} onChange={(e) => { setEmail(e.target.value); requestId.current = null; }}
                className="w-full rounded-lg border border-gray-300 p-3" />
            </div>
            <div>
              <label htmlFor="support-description" className="mb-1 block font-medium">{t("description")}</label>
              <textarea id="support-description" required minLength={10} maxLength={5000} rows={5} dir="auto"
                aria-describedby="support-hint" disabled={pending} value={description}
                onChange={(e) => { setDescription(e.target.value); requestId.current = null; }}
                className="w-full rounded-lg border border-gray-300 p-3" />
              <p id="support-hint" className="mt-1 text-xs text-gray-600">{t("hint")}</p>
            </div>
            <div hidden aria-hidden="true">
              <label htmlFor="support-website">Website</label>
              <input id="support-website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
            </div>
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
            <button type="submit" disabled={pending} className="w-full rounded-lg bg-brand-primary px-4 py-3 font-semibold text-white disabled:opacity-50">
              {t(pending ? "sending" : "send")}
            </button>
          </form>
        )}
      </dialog>
    </>
  );
}
