"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ProfilePhotoUpload } from "./ProfilePhotoUpload";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";

// All users are in Egypt, so the +2 country code is a fixed prefix shown
// next to the input rather than something the user has to type themselves.
const LOCAL_PHONE_RE = /^\d{11}$/;

type FormValues = { display_name: string; phone_number?: string };

interface ProfileFormProps {
  defaultValues?: {
    display_name?: string;
    profile_photo_url?: string | null;
    phone_number?: string | null;
  };
  onSubmit: (data: FormValues, photo: File | null) => Promise<void>;
  submitLabel?: string;
  showPhone?: boolean;
}

export function ProfileForm({
  defaultValues,
  onSubmit,
  submitLabel,
  showPhone = false,
}: ProfileFormProps) {
  const t = useTranslations("profileForm");
  const [photo, setPhoto] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const schema = z
    .object({
      display_name: z.string().trim().min(2, t("errors.minChars")).max(50, t("errors.maxChars")),
      phone_number: z.string().trim().optional(),
    })
    .superRefine((data, ctx) => {
      if (showPhone && !LOCAL_PHONE_RE.test(data.phone_number ?? "")) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["phone_number"], message: t("errors.phoneInvalid") });
      }
    });

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: defaultValues?.display_name ?? "",
      phone_number: (defaultValues?.phone_number ?? "").replace(/^\+2/, ""),
    },
  });

  const handle = async (data: FormValues) => {
    setLoading(true);
    setError("");
    try {
      const payload = showPhone && data.phone_number
        ? { ...data, phone_number: `+2${data.phone_number}` }
        : data;
      await onSubmit(payload, photo);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? t("errors.generic"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(handle)} className="space-y-5">
      <ProfilePhotoUpload onFile={setPhoto} currentUrl={defaultValues?.profile_photo_url} />

      <div className="flex flex-col gap-1">
        <label className="text-label text-dash-text-muted">{t("displayNameLabel")}</label>
        <input
          {...register("display_name")}
          placeholder={t("displayNamePlaceholder")}
          className="px-3 py-2.5 bg-dash-surface shadow-sm border border-dash-border rounded-xl text-body-sm text-dash-navy outline-none focus:border-dash-primary transition-colors"
        />
        {errors.display_name && <p className="text-caption text-content-destructive">{errors.display_name.message}</p>}
      </div>

      {showPhone && (
        <div className="flex flex-col gap-1">
          <label className="text-label text-dash-text-muted">{t("phoneLabel")}</label>
          <div className="relative" dir="ltr">
            <span className="absolute inset-y-0 start-0 flex items-center ps-3 text-body-sm text-dash-text-muted pointer-events-none">
              +2
            </span>
            <input
              type="tel"
              inputMode="numeric"
              {...register("phone_number")}
              placeholder={t("phonePlaceholder")}
              maxLength={11}
              className="w-full ps-9 pe-3 py-2.5 bg-dash-surface shadow-sm border border-dash-border rounded-xl text-body-sm text-dash-navy outline-none focus:border-dash-primary transition-colors"
            />
          </div>
          {errors.phone_number && <p className="text-caption text-content-destructive">{errors.phone_number.message}</p>}
        </div>
      )}

      {error && <p className="text-caption text-content-destructive">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-dash-primary hover:opacity-90 text-white rounded-xl font-semibold disabled:opacity-50 transition-opacity"
      >
        {loading && <Spinner />}
        {loading ? t("saving") : (submitLabel ?? t("save"))}
      </button>
    </form>
  );
}
