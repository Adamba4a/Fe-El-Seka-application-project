"use client";

import { useEffect, useRef, useState } from "react";

interface ProfilePhotoUploadProps {
  onFile: (file: File) => void;
  currentUrl?: string | null;
}

const ALLOWED = ["image/jpeg", "image/png"];
const MAX_BYTES = 5 * 1024 * 1024;

export function ProfilePhotoUpload({ onFile, currentUrl }: ProfilePhotoUploadProps) {
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
      setError("Only JPEG and PNG files are accepted");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("Photo must be under 5 MB");
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
        className="w-20 h-20 rounded-full border-2 border-dashed border-border-default flex items-center justify-center overflow-hidden cursor-pointer hover:border-brand-primary transition-colors focus:outline-none focus:border-border-focus"
        aria-label="Upload profile photo"
      >
        {preview ? (
          <img src={preview} alt="Profile" className="w-full h-full object-cover" />
        ) : (
          <span className="text-3xl text-content-muted">👤</span>
        )}
      </button>
      <button type="button" onClick={() => ref.current?.click()} className="text-body-sm text-brand-primary underline">
        {preview ? "Change photo" : "Upload photo (optional)"}
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
