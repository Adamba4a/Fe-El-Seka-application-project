import { env } from "../env";

const base = env.apiUrl;

// Mirrors wallet_topup_service._DEFAULT_VODAFONE_CASH_NUMBER — the sentinel
// the backend returns when an operator hasn't set the real Vodafone Cash
// number yet, so the frontend must never display it as if it were real.
export const VODAFONE_CASH_NUMBER_NOT_CONFIGURED = "VODAFONE_CASH_NUMBER_NOT_CONFIGURED";

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export interface TopupSettings {
  vodafone_cash_number: string;
  is_locked: boolean;
  support_email: string | null;
}

export interface TopupSubmitResponse {
  id: string;
  status: string;
  amount_egp: string;
  payment_reference: string;
  created_at: string;
}

export async function getSettings(token: string): Promise<TopupSettings> {
  const res = await fetch(`${base}/api/wallet/topup/settings`, {
    headers: authHeaders(token),
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}

export async function submitRequest(
  token: string,
  amountEgp: string,
  paymentReference: string,
  screenshot: File,
): Promise<TopupSubmitResponse> {
  const form = new FormData();
  form.append("amount_egp", amountEgp);
  form.append("payment_reference", paymentReference);
  form.append("screenshot", screenshot);

  const res = await fetch(`${base}/api/wallet/topup`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  const json = await res.json();
  if (!res.ok) throw json;
  return json;
}
