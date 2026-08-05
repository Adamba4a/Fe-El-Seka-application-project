import type { Locale } from "@fe-el-seka/shared";
import type { AbstractIntlMessages } from "next-intl";
import { env } from "../env";
import { locales } from "./config";
import bundledEnMessages from "../../../messages/en.json";

// Public content bucket — mirrors the plain bucket-name convention used by
// services/api/app/services/storage_service.py (e.g. "profile-photos").
const _BUCKET = "app-content";
const _REFRESH_INTERVAL_MS = 5 * 60 * 1000;

type MessageCatalog = {
  locale: Locale;
  version: string;
  messages: AbstractIntlMessages;
};

const _bundledFallback: MessageCatalog = {
  locale: "en",
  version: "bundled",
  messages: bundledEnMessages,
};

const _cache = new Map<Locale, MessageCatalog>();
let _initPromise: Promise<void> | null = null;
let _lastLoadedAt = 0;

function _catalogUrl(locale: Locale): string {
  return `${env.supabaseUrl}/storage/v1/object/public/${_BUCKET}/messages/${locale}.json`;
}

async function _fetchCatalog(locale: Locale): Promise<MessageCatalog | null> {
  try {
    const res = await fetch(_catalogUrl(locale), { cache: "no-store" });
    if (!res.ok) return null;
    const data = (await res.json()) as MessageCatalog;
    if (!data || typeof data.messages !== "object") return null;
    return data;
  } catch {
    return null;
  }
}

async function _loadAll(): Promise<void> {
  const fetched = await Promise.all(locales.map((locale) => _fetchCatalog(locale)));
  const anyLoaded = fetched.some((catalog) => catalog !== null);

  if (!anyLoaded) {
    // Storage unreachable — degrade to the bundled English catalog for every
    // locale rather than fail to render (see contracts/message-catalog.md).
    for (const locale of locales) {
      _cache.set(locale, { ..._bundledFallback, locale });
    }
    return;
  }

  fetched.forEach((catalog, i) => {
    const locale = locales[i];
    if (catalog) {
      _cache.set(locale, catalog);
    } else if (!_cache.has(locale)) {
      _cache.set(locale, { ..._bundledFallback, locale });
    }
  });
}

async function _ensureLoaded(): Promise<void> {
  if (!_initPromise) {
    // Cold start: nothing cached yet, so this request must wait for the load.
    _initPromise = _loadAll().then(() => {
      _lastLoadedAt = Date.now();
    });
    await _initPromise;
    return;
  }

  const isStale = Date.now() - _lastLoadedAt > _REFRESH_INTERVAL_MS;
  if (isStale) {
    // Stale-while-revalidate: refresh in the background and let this
    // request go through with the last-known-good cache immediately,
    // rather than blocking on a fetch.
    _initPromise = _loadAll().then(() => {
      _lastLoadedAt = Date.now();
    });
    _initPromise.catch(() => {
      // Keep serving the last-known-good cache on a failed background refresh.
    });
    return;
  }

  await _initPromise;
}

export async function getMessages(locale: Locale): Promise<AbstractIntlMessages> {
  await _ensureLoaded();
  return _cache.get(locale)?.messages ?? _bundledFallback.messages;
}
