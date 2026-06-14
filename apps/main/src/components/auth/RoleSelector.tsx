"use client";

interface RoleSelectorProps {
  value: "passenger" | "driver" | null;
  onChange: (role: "passenger" | "driver") => void;
}

const roles = [
  {
    id: "passenger" as const,
    title: "Passenger",
    description: "Find and join rides that match your route",
    icon: "🧑‍💼",
  },
  {
    id: "driver" as const,
    title: "Driver",
    description: "Post your existing routes and share rides",
    icon: "🚗",
  },
];

export function RoleSelector({ value, onChange }: RoleSelectorProps) {
  return (
    <div className="grid grid-cols-1 gap-3">
      {roles.map((role) => (
        <button
          key={role.id}
          type="button"
          onClick={() => onChange(role.id)}
          className={`flex items-start gap-4 p-4 border-2 rounded-lg text-left transition-colors ${
            value === role.id
              ? "border-blue-600 bg-blue-50"
              : "border-gray-200 hover:border-gray-300"
          }`}
        >
          <span className="text-3xl">{role.icon}</span>
          <div>
            <p className="font-semibold">{role.title}</p>
            <p className="text-sm text-gray-500">{role.description}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
