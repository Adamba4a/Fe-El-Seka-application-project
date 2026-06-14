import type { VerificationStatus } from "@fe-el-seka/shared";

const STATUS_CONFIG = {
  unverified: { icon: "⚪", label: "Not submitted", color: "text-gray-500" },
  pending_review: { icon: "⏳", label: "Under review", color: "text-yellow-600" },
  verified: { icon: "✅", label: "Verified", color: "text-green-600" },
  rejected: { icon: "❌", label: "Rejected", color: "text-red-600" },
  suspended: { icon: "🚫", label: "Suspended", color: "text-red-700" },
};

interface VerificationStatusProps {
  status: VerificationStatus;
}

export function VerificationStatusBadge({ status }: VerificationStatusProps) {
  const cfg = STATUS_CONFIG[status.verification_status as keyof typeof STATUS_CONFIG] ?? STATUS_CONFIG.unverified;

  return (
    <div className="space-y-2">
      <div className={`flex items-center gap-2 font-medium ${cfg.color}`}>
        <span>{cfg.icon}</span>
        <span>{cfg.label}</span>
        {status.attempt_number && (
          <span className="text-xs text-gray-400 font-normal">(Attempt {status.attempt_number}/3)</span>
        )}
      </div>
      {status.rejection_reason && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">
          <strong>Reason:</strong> {status.rejection_reason}
        </div>
      )}
    </div>
  );
}
