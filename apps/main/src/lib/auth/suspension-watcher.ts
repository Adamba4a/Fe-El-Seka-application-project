"use client";

// The API rejects every authenticated call from a suspended account with a
// 401 whose body carries {error: "account_suspended", ...} (FastAPI wraps it
// under "detail"). Individual pages/components each had their own ad hoc
// catch-block fallback text, so a suspended user saw a different, often
// generic error depending on which fetch happened to fail first. Patching
// fetch once here lets a single listener (AppShell) show one consistent,
// clearly styled screen no matter which API call trips it.

type Listener = () => void;

const listeners = new Set<Listener>();
let installed = false;

function extractError(body: unknown): { error?: string } | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (detail && typeof detail === "object") return detail as { error?: string };
  return body as { error?: string };
}

function install() {
  if (installed || typeof window === "undefined") return;
  installed = true;
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const res = await originalFetch(...args);
    if (res.status === 401) {
      res
        .clone()
        .json()
        .then((body) => {
          if (extractError(body)?.error === "account_suspended") {
            listeners.forEach((listener) => listener());
          }
        })
        .catch(() => {});
    }
    return res;
  };
}

export function onAccountSuspended(listener: Listener): () => void {
  install();
  listeners.add(listener);
  return () => listeners.delete(listener);
}
