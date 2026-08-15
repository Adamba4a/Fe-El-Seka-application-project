"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ProfilePhotoUpload } from "./ProfilePhotoUpload";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";

const PHONE_RE = /^\+[1-9]\d{6,14}$/;

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
  photoRequired?: boolean;
}

export function ProfileForm({
  defaultValues,
  onSubmit,
  submitLabel,
  showPhone = false,
  photoRequired = false,
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
      if (showPhone && !PHONE_RE.test(data.phone_number ?? "")) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["phone_number"], message: t("errors.phoneInvalid") });
      }
    });

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: defaultValues?.display_name ?? "",
      phone_number: defaultValues?.phone_number ?? "",
    },
  });

  const handle = async (data: FormValues) => {
    if (photoRequired && !photo && !defaultValues?.profile_photo_url) {
      setError(t("errors.photoRequired"));
      return;
    }
    setLoading(true);
    setError("");
    try {
      await onSubmit(data, photo);
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
          <input
            type="tel"
            {...register("phone_number")}
            placeholder={t("phonePlaceholder")}
            maxLength={16}
            className="px-3 py-2.5 bg-dash-surface shadow-sm border border-dash-border rounded-xl text-body-sm text-dash-navy outline-none focus:border-dash-primary transition-colors"
          />
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
