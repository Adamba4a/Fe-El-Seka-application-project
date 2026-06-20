"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ProfilePhotoUpload } from "./ProfilePhotoUpload";
import { useState } from "react";
import { Spinner } from "@/components/ui/Spinner";

const schema = z.object({
  display_name: z.string().trim().min(2, "Min 2 characters").max(50, "Max 50 characters"),
});

type FormValues = z.infer<typeof schema>;

interface ProfileFormProps {
  defaultValues?: { display_name?: string; profile_photo_url?: string | null };
  onSubmit: (data: FormValues, photo: File | null) => Promise<void>;
  submitLabel?: string;
}

export function ProfileForm({ defaultValues, onSubmit, submitLabel = "Save" }: ProfileFormProps) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { display_name: defaultValues?.display_name ?? "" },
  });

  const handle = async (data: FormValues) => {
    setLoading(true);
    setError("");
    try {
      await onSubmit(data, photo);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(handle)} className="space-y-5">
      <ProfilePhotoUpload onFile={setPhoto} currentUrl={defaultValues?.profile_photo_url} />

      <div className="flex flex-col gap-1">
        <label className="text-label text-content-secondary">Display name</label>
        <input
          {...register("display_name")}
          placeholder="Your name"
          className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
        />
        {errors.display_name && <p className="text-caption text-content-destructive">{errors.display_name.message}</p>}
      </div>

      {error && <p className="text-caption text-content-destructive">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
      >
        {loading && <Spinner />}
        {loading ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
