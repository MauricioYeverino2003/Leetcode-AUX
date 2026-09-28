/**
 * Service worker.
 *
 * Chrome shuts this down whenever it is idle and restarts it on the next event,
 * so nothing may be kept in memory here. Anything that has to survive belongs
 * in chrome.storage or Supabase.
 *
 * For now it has one job: clicking the toolbar icon opens the side panel.
 */
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error: unknown) => console.error("[LC-AUX] could not set side panel behavior", error));
