"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ProfilePhotoUpload } from "./ProfilePhotoUpload";
import { useState } from "react";

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
        <label className="text-sm font-medium">Display name</label>
        <input
          {...register("display_name")}
          placeholder="Your name"
          className="px-3 py-2 border rounded-md text-sm outline-none focus:ring-2 focus:ring-blue-500"
        />
        {errors.display_name && <p className="text-red-500 text-xs">{errors.display_name.message}</p>}
      </div>

      {error && <p className="text-red-500 text-xs">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 px-4 bg-blue-600 text-white rounded-md font-medium disabled:opacity-50"
      >
        {loading ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
