"use client";

import { useRef, useState } from "react";

interface DocumentUploadProps {
  label: string;
  onFile: (file: File) => void;
  required?: boolean;
}

const ALLOWED = ["image/jpeg", "image/png"];
const MAX_BYTES = 10 * 1024 * 1024;

export function DocumentUpload({ label, onFile, required }: DocumentUploadProps) {
  const ref = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");

  const handleFile = (file: File) => {
    setError("");
    if (!ALLOWED.includes(file.type)) {
      setError("Only JPEG and PNG files are accepted");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("File must be under 10 MB");
      return;
    }
    setPreview(URL.createObjectURL(file));
    setFileName(file.name);
    onFile(file);
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div
        onClick={() => ref.current?.click()}
        className="relative w-full aspect-video border-2 border-dashed border-gray-300 rounded-lg overflow-hidden flex items-center justify-center cursor-pointer hover:border-blue-400 transition-colors bg-gray-50"
      >
        {preview ? (
          <img src={preview} alt={label} className="w-full h-full object-contain" />
        ) : (
          <div className="text-center text-gray-400 p-4">
            <p className="text-2xl mb-1">📄</p>
            <p className="text-xs">Click to upload</p>
            <p className="text-xs">JPEG or PNG, max 10 MB</p>
          </div>
        )}
      </div>
      {fileName && <p className="text-xs text-gray-500">{fileName}</p>}
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
