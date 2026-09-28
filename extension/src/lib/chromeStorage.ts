import type { SupportedStorage } from "@supabase/supabase-js";

/**
 * Session storage for Supabase auth, backed by chrome.storage.local.
 *
 * This is what replaces the cookie handling from the Next.js app. Cookies were
 * only ever a way to hand the session to a rendering server; an extension has
 * no such server, and cookies on a chrome-extension:// origin are not a useful
 * place to keep anything. chrome.storage.local survives the panel closing and
 * is readable from the service worker as well as the panel.
 *
 * It works because Supabase's storage contract allows these methods to return
 * promises — chrome.storage is async, unlike the localStorage it stands in for.
 */
export const chromeStorage: SupportedStorage = {
  async getItem(key) {
    const result = await chrome.storage.local.get(key);
    const value: unknown = result[key];
    return typeof value === "string" ? value : null;
  },

  async setItem(key, value) {
    await chrome.storage.local.set({ [key]: value });
  },

  async removeItem(key) {
    await chrome.storage.local.remove(key);
  },
};
