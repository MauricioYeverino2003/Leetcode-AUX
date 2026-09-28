import { createClient } from "@supabase/supabase-js";

import { chromeStorage } from "./chromeStorage";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // Vite inlines env vars at build time, so this means the bundle was built
  // without them — fail loudly rather than render a blank panel.
  throw new Error(
    "Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY. Add them to extension/.env.local and rebuild.",
  );
}

/**
 * One client for the lifetime of the page.
 *
 * Note this is the opposite of the rule in the Next.js app, where the server
 * client had to be created per request so sessions could not leak between
 * users. An extension page only ever serves one user — the person whose browser
 * profile it is running in — so a module-level singleton is correct here.
 */
export const supabase = createClient(url, anonKey, {
  auth: {
    storage: chromeStorage,
    persistSession: true,
    autoRefreshToken: true,
    // There is never an OAuth fragment to parse in an extension page's URL.
    detectSessionInUrl: false,
  },
});
