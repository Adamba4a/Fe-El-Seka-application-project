"use client";

import { useState } from "react";

interface DocumentViewerProps {
  signedUrls: string[];
  labels?: string[];
}

export function DocumentViewer({ signedUrls, labels }: DocumentViewerProps) {
  const [selected, setSelected] = useState(0);

  if (!signedUrls.length) return <p className="text-gray-400 text-sm">No documents</p>;

  return (
    <div className="space-y-3">
      {signedUrls.length > 1 && (
        <div className="flex gap-2">
          {signedUrls.map((_, i) => (
            <button
              key={i}
              onClick={() => setSelected(i)}
              className={`px-3 py-1 rounded text-sm border ${selected === i ? "bg-gray-900 text-white" : "bg-white text-gray-700 hover:bg-gray-50"}`}
            >
              {labels?.[i] ?? `Document ${i + 1}`}
            </button>
          ))}
        </div>
      )}
      <div className="border rounded overflow-hidden">
        <img
          src={signedUrls[selected]}
          alt={labels?.[selected] ?? `Document ${selected + 1}`}
          className="max-w-full max-h-[600px] object-contain mx-auto block"
        />
      </div>
    </div>
  );
}
