"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";

const currentYear = new Date().getFullYear();

type FormValues = {
  plate_number: string;
  make: string;
  model: string;
  year: number;
  color: string;
  seat_count: number;
};

interface VehicleRegistrationFormProps {
  onSubmit: (data: FormValues) => Promise<void>;
}

export function VehicleRegistrationForm({ onSubmit }: VehicleRegistrationFormProps) {
  const t = useTranslations("vehicleForm");

  const schema = z.object({
    plate_number: z
      .string()
      .min(1, t("errors.required"))
      .regex(
        /^[؀-ۿa-zA-Z](\s?[؀-ۿa-zA-Z]){0,2}\s?\d{1,4}$|^\d{1,4}\s?[؀-ۿa-zA-Z](\s?[؀-ۿa-zA-Z]){0,2}$|^\d{1,5}$/,
        t("errors.invalidPlate")
      ),
    make: z.string().min(1, t("errors.required")),
    model: z.string().min(1, t("errors.required")),
    year: z.number().int().min(2000, t("errors.minYear")).max(currentYear, t("errors.maxYear", { year: currentYear })),
    color: z.string().min(1, t("errors.required")),
    seat_count: z.number().int().min(2, t("errors.minSeats")).max(7, t("errors.maxSeats")),
  });

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const fields: { key: keyof FormValues; label: string; type?: string; placeholder: string }[] = [
    { key: "plate_number", label: t("plateNumberLabel"), placeholder: t("plateNumberPlaceholder") },
    { key: "make", label: t("makeLabel"), placeholder: t("makePlaceholder") },
    { key: "model", label: t("modelLabel"), placeholder: t("modelPlaceholder") },
    { key: "year", label: t("yearLabel"), type: "number", placeholder: t("yearPlaceholder") },
    { key: "color", label: t("colorLabel"), placeholder: t("colorPlaceholder") },
    { key: "seat_count", label: t("seatsLabel"), type: "number", placeholder: t("seatsPlaceholder") },
  ];

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {fields.map(({ key, label, type, placeholder }) => (
        <div key={key} className="flex flex-col gap-1">
          <label className="text-label text-content-secondary">{label}</label>
          <input
            {...register(key, type === "number" ? { valueAsNumber: true } : {})}
            type={type ?? "text"}
            placeholder={placeholder}
            className="px-3 py-2 border border-border-default rounded-md text-body-sm outline-none focus:border-border-focus transition-colors"
          />
          {errors[key] && <p className="text-caption text-content-destructive">{errors[key]?.message as string}</p>}
        </div>
      ))}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-opacity"
      >
        {isSubmitting && <Spinner />}
        {isSubmitting ? t("registering") : t("register")}
      </button>
    </form>
  );
}
