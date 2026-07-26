"use client";

import { useState } from "react";
import type { AIReadout as AIReadoutData } from "@fe-el-seka/shared";

interface AIReadoutProps {
  readout: AIReadoutData | null;
  userName: string;
}

function scoreBadge(score: number | null, goodAbove: number) {
  if (score === null) {
    return <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">No score</span>;
  }
  const pct = Math.round(score * 100);
  const color =
    score >= goodAbove
      ? "bg-green-100 text-green-800"
      : score >= goodAbove / 2
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>{pct}%</span>;
}

export function AIReadout({ readout, userName }: AIReadoutProps) {
  const [expanded, setExpanded] = useState(false);

  if (!readout) {
    return (
      <div className="border rounded p-4 bg-gray-50 text-sm text-gray-500">
        No AI read-out available for this submission.
      </div>
    );
  }

  return (
    <div className="border rounded p-4 space-y-3 bg-gray-50">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">AI Read-out (advisory only)</h2>
        <span className="text-xs text-gray-400">{readout.model_version}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-gray-500 text-xs mb-1">Name match vs. &quot;{userName}&quot;</div>
          {scoreBadge(readout.name_match_score, 0.8)}
        </div>
        <div>
          <div className="text-gray-500 text-xs mb-1">Selfie / ID face match</div>
          {readout.face_match_score !== null ? (
            scoreBadge(readout.face_match_score, 0.6)
          ) : readout.selfie_face_detected === false ? (
            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">No face detected in selfie</span>
          ) : readout.id_face_detected === false ? (
            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">No face detected in ID photo</span>
          ) : (
            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">No selfie on file</span>
          )}
        </div>
      </div>

      {readout.reasons && readout.reasons.length > 0 && (
        <ul className="text-sm text-gray-700 list-disc pl-5 space-y-0.5">
          {readout.reasons.map((reason: string, i: number) => (
            <li key={i}>{reason}</li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="text-xs text-gray-500 underline"
      >
        {expanded ? "Hide" : "Show"} raw OCR text
      </button>
      {expanded && (
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <div className="text-gray-500 mb-1">Front</div>
            <pre className="whitespace-pre-wrap bg-white border rounded p-2 max-h-40 overflow-y-auto">
              {readout.ocr_text_front || "(empty)"}
            </pre>
          </div>
          <div>
            <div className="text-gray-500 mb-1">Back</div>
            <pre className="whitespace-pre-wrap bg-white border rounded p-2 max-h-40 overflow-y-auto">
              {readout.ocr_text_back || "(empty)"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
