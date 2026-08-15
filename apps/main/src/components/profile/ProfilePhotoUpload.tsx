"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

interface ProfilePhotoUploadProps {
  onFile: (file: File) => void;
  currentUrl?: string | null;
}

const ALLOWED = ["image/jpeg", "image/png"];
const MAX_BYTES = 5 * 1024 * 1024;

export function ProfilePhotoUpload({ onFile, currentUrl }: ProfilePhotoUploadProps) {
  const t = useTranslations("profileForm");
  const ref = useRef<HTMLInputElement>(null);
  const objectUrlRef = useRef<string | null>(null);
  const [preview, setPreview] = useState<string | null>(currentUrl ?? null);
  const [error, setError] = useState("");

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const handleFile = (file: File) => {
    setError("");
    if (!ALLOWED.includes(file.type)) {
      setError(t("errors.invalidPhotoType"));
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(t("errors.photoTooLarge"));
      return;
    }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    setPreview(url);
    onFile(file);
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        onClick={() => ref.current?.click()}
        className="w-28 h-28 rounded-full bg-dash-surface shadow-md ring-4 ring-white flex items-center justify-center overflow-hidden cursor-pointer hover:opacity-90 transition-opacity focus:outline-none"
        aria-label={t("uploadPhotoAriaLabel")}
      >
        {preview ? (
          <img src={preview} alt={t("uploadPhotoAriaLabel")} className="w-full h-full object-cover" />
        ) : (
          <span className="text-4xl text-dash-text-muted">👤</span>
        )}
      </button>
      <button type="button" onClick={() => ref.current?.click()} className="text-body-sm text-dash-primary font-semibold hover:underline">
        {preview ? t("changePhoto") : t("uploadPhoto")}
      </button>
      {error && <p className="text-caption text-content-destructive">{error}</p>}
      <input
        ref={ref}
        type="file"
        accept="image/jpeg,image/png"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
    </div>
  );
}
