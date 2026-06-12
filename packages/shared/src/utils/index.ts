export function formatPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.startsWith("20") && digits.length === 12) {
    return `+${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
  }
  return phone;
}

export function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("en-EG", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
