"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Spinner } from "@/components/ui/Spinner";

const currentYear = new Date().getFullYear();

const schema = z.object({
  plate_number: z
    .string()
    .min(1, "Required")
    .regex(
      /^[؀-ۿa-zA-Z]{1,3}\s?\d{1,4}$|^\d{1,4}\s?[؀-ۿa-zA-Z]{1,3}$|^\d{1,5}$/,
      "Invalid plate format"
    ),
  make: z.string().min(1, "Required"),
  model: z.string().min(1, "Required"),
  year: z.number().int().min(2000, "Min year 2000").max(currentYear, `Max year ${currentYear}`),
  color: z.string().min(1, "Required"),
  seat_count: z.number().int().min(2, "Min 2 seats").max(7, "Max 7 seats"),
});

type FormValues = z.infer<typeof schema>;

interface VehicleRegistrationFormProps {
  onSubmit: (data: FormValues) => Promise<void>;
}

export function VehicleRegistrationForm({ onSubmit }: VehicleRegistrationFormProps) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const fields: { key: keyof FormValues; label: string; type?: string; placeholder: string }[] = [
    { key: "plate_number", label: "Plate Number", placeholder: "e.g. أ ب ج 1234 or ABC 1234" },
    { key: "make", label: "Make (Brand)", placeholder: "e.g. Toyota" },
    { key: "model", label: "Model", placeholder: "e.g. Corolla" },
    { key: "year", label: "Year", type: "number", placeholder: "e.g. 2021" },
    { key: "color", label: "Color", placeholder: "e.g. White" },
    { key: "seat_count", label: "Passenger Seats (2–7, excluding driver)", type: "number", placeholder: "e.g. 4" },
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
        className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
      >
        {isSubmitting && <Spinner />}
        {isSubmitting ? "Registering…" : "Register Vehicle"}
      </button>
    </form>
  );
}
