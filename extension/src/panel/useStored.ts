import { useEffect, useState } from "react";

/** A value in chrome.storage.local, kept live: the content script writes
 *  whenever something changes on the page, and onChanged delivers it here. */
export function useStored<T>(key: string): T | null {
  const [value, setValue] = useState<T | null>(null);

  useEffect(() => {
    let cancelled = false;

    chrome.storage.local.get(key).then((result) => {
      if (!cancelled) setValue((result[key] as T | undefined) ?? null);
    });

    const onChanged = (changes: { [key: string]: chrome.storage.StorageChange }, area: string) => {
      if (area === "local" && changes[key]) {
        setValue((changes[key].newValue as T | undefined) ?? null);
      }
    };

    chrome.storage.onChanged.addListener(onChanged);

    return () => {
      cancelled = true;
      chrome.storage.onChanged.removeListener(onChanged);
    };
  }, [key]);

  return value;
}
