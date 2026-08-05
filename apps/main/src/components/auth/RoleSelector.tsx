"use client";

import { useTranslations } from "next-intl";

interface RoleSelectorProps {
  value: "passenger" | "driver" | null;
  onChange: (role: "passenger" | "driver") => void;
}

const roles = [
  {
    id: "passenger" as const,
    titleKey: "passengerTitle" as const,
    descriptionKey: "passengerDescription" as const,
    icon: "🧑‍💼",
  },
  {
    id: "driver" as const,
    titleKey: "driverTitle" as const,
    descriptionKey: "driverDescription" as const,
    icon: "🚗",
  },
];

export function RoleSelector({ value, onChange }: RoleSelectorProps) {
  const t = useTranslations("auth.roleSelect");
  return (
    <div className="grid grid-cols-1 gap-3">
      {roles.map((role) => (
        <button
          key={role.id}
          type="button"
          onClick={() => onChange(role.id)}
          className={`flex items-start gap-4 p-4 border-2 rounded-xl text-left transition-colors ${
            value === role.id
              ? "border-brand-primary bg-status-scheduled-bg"
              : "border-border-default hover:border-brand-primary"
          }`}
        >
          <span className="text-3xl">{role.icon}</span>
          <div>
            <p className="text-h3 text-content-primary">{t(role.titleKey)}</p>
            <p className="text-body-sm text-content-muted mt-0.5">{t(role.descriptionKey)}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
