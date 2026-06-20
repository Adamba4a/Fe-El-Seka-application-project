"use client";

import { useEffect, useRef, useState } from "react";

interface DocumentUploadProps {
  label: string;
  onFile: (file: File) => void;
  required?: boolean;
}

const ALLOWED = ["image/jpeg", "image/png"];
const MAX_BYTES = 10 * 1024 * 1024;

export function DocumentUpload({ label, onFile, required }: DocumentUploadProps) {
  const ref = useRef<HTMLInputElement>(null);
  const objectUrlRef = useRef<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");

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
      setError("File must be under 10 MB");
      return;
    }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    setPreview(url);
    setFileName(file.name);
    onFile(file);
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="text-label text-content-secondary">
        {label} {required && <span className="text-content-destructive">*</span>}
      </label>
      <div
        onClick={() => ref.current?.click()}
        className="relative w-full aspect-video border-2 border-dashed border-border-default rounded-xl overflow-hidden flex items-center justify-center cursor-pointer hover:border-brand-primary transition-colors bg-surface-bg"
        style={{ maxHeight: 120 }}
      >
        {preview ? (
          <img src={preview} alt={label} className="w-full h-full object-contain" />
        ) : (
          <div className="text-center text-content-muted p-4">
            <p className="text-2xl mb-1">📄</p>
            <p className="text-caption">Click to upload</p>
            <p className="text-caption">JPEG or PNG, max 10 MB</p>
          </div>
        )}
      </div>
      {fileName && <p className="text-caption text-content-muted">{fileName}</p>}
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
