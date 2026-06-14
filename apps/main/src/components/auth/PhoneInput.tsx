"use client";

import { forwardRef } from "react";

interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
}

export const PhoneInput = forwardRef<HTMLInputElement, PhoneInputProps>(
  ({ value, onChange, error, disabled }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      let raw = e.target.value.replace(/\D/g, "");
      if (raw.startsWith("20")) raw = raw.slice(2);
      if (raw.startsWith("0")) raw = raw.slice(1);
      const truncated = raw.slice(0, 10);
      onChange(truncated ? `+20${truncated}` : "");
    };

    const display = value.startsWith("+20") ? value.slice(3) : value;

    return (
      <div className="flex flex-col gap-1">
        <div className="flex items-center border rounded-md overflow-hidden focus-within:ring-2 focus-within:ring-blue-500">
          <span className="px-3 py-2 bg-gray-100 border-r text-gray-600 text-sm font-medium select-none">
            +20
          </span>
          <input
            ref={ref}
            type="tel"
            inputMode="numeric"
            placeholder="1xxxxxxxxx"
            value={display}
            onChange={handleChange}
            disabled={disabled}
            className="flex-1 px-3 py-2 outline-none text-sm disabled:bg-gray-50"
            maxLength={10}
          />
        </div>
        {error && <p className="text-red-500 text-xs">{error}</p>}
      </div>
    );
  }
);
PhoneInput.displayName = "PhoneInput";
