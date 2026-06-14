"use client";

import { useRef, useState } from "react";

interface ProfilePhotoUploadProps {
  onFile: (file: File) => void;
  currentUrl?: string | null;
}

const ALLOWED = ["image/jpeg", "image/png"];
const MAX_BYTES = 5 * 1024 * 1024;

export function ProfilePhotoUpload({ onFile, currentUrl }: ProfilePhotoUploadProps) {
  const ref = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(currentUrl ?? null);
  const [error, setError] = useState("");

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
    setPreview(URL.createObjectURL(file));
    onFile(file);
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        onClick={() => ref.current?.click()}
        className="w-24 h-24 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center overflow-hidden cursor-pointer hover:border-blue-400 transition-colors"
      >
        {preview ? (
          <img src={preview} alt="Profile" className="w-full h-full object-cover" />
        ) : (
          <span className="text-3xl text-gray-300">👤</span>
        )}
      </div>
      <button type="button" onClick={() => ref.current?.click()} className="text-sm text-blue-600 underline">
        {preview ? "Change photo" : "Upload photo (optional)"}
      </button>
      {error && <p className="text-red-500 text-xs">{error}</p>}
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
