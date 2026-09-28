/**
 * MAIN-world script — reads the user's code out of the Monaco editor.
 *
 * This runs in the page's own JavaScript world (`"world": "MAIN"` in the
 * manifest), unlike content.ts. That is the only way to reach window.monaco:
 * content scripts live in an isolated world with their own wrappers around DOM
 * objects and cannot see page globals. Scraping the DOM is not an alternative,
 * because Monaco virtualizes — only the lines currently scrolled into view
 * exist as elements.
 *
 * The price of running here is that chrome.* is unavailable, so results go to
 * content.ts over window.postMessage. Everything sent is plain data.
 *
 * This is also the least trusted place in the extension: page code can see and
 * call anything defined here. It therefore holds no secrets and no auth state.
 */

import { BRIDGE_SOURCE, type CodeMessage, type CodeRequest } from "./lib/code";

const LOG = "[LC-AUX:main]";
const DEBOUNCE_MS = 500;
const MONACO_POLL_MS = 500;

// Minimal view of the Monaco API surface we touch. Typed here rather than via
// the monaco-editor package: we never import it, only find it on the page.
type Disposable = { dispose(): void };

type Model = {
  uri: { toString(): string };
  getValue(): string;
  getLanguageId(): string;
  isDisposed(): boolean;
  onDidChangeContent(listener: () => void): Disposable;
};

type Editor = {
  getModel(): Model | null;
  getDomNode(): HTMLElement | null;
  onDidChangeModel(listener: () => void): Disposable;
  onDidDispose(listener: () => void): Disposable;
};

type Monaco = {
  editor: {
    getModels(): Model[];
    onDidCreateModel(listener: (model: Model) => void): Disposable;
    // Added in Monaco 0.36; older builds have only the model API.
    getEditors?: () => Editor[];
    onDidCreateEditor?: (listener: (editor: Editor) => void) => Disposable;
  };
};

declare global {
  interface Window {
    monaco?: Monaco;
  }
}

// ---------------------------------------------------------------------------
// Choosing what to read
// ---------------------------------------------------------------------------

function isVisible(node: HTMLElement | null): node is HTMLElement {
  return node !== null && node.isConnected && node.offsetWidth > 0 && node.offsetHeight > 0;
}

/** The editor the user is typing in: the largest visible one that has a model.
 *  LeetCode may keep other Monaco instances around (test-case input, hidden
 *  language buffers); size and visibility pick the main one. */
function pickEditor(monaco: Monaco): { editor: Editor; model: Model } | null {
  const editors = monaco.editor.getEditors?.() ?? [];

  const candidates = editors.flatMap((editor) => {
    const model = editor.getModel();
    const node = editor.getDomNode();
    return model && isVisible(node) ? [{ editor, model, area: node.offsetWidth * node.offsetHeight }] : [];
  });

  candidates.sort((a, b) => b.area - a.area);
  const best = candidates[0];
  return best ? { editor: best.editor, model: best.model } : null;
}

/** Fallback when getEditors() is missing or nothing is visible: prefer a
 *  model in a real language over plaintext, then the one with the most in it. */
function pickModel(monaco: Monaco): Model | null {
  const live = monaco.editor.getModels().filter((m) => !m.isDisposed());
  const code = live.filter((m) => m.getLanguageId() !== "plaintext");
  const pool = code.length > 0 ? code : live;
  pool.sort((a, b) => b.getValue().length - a.getValue().length);
  return pool[0] ?? null;
}

// ---------------------------------------------------------------------------
// Publishing
// ---------------------------------------------------------------------------

function publish(monaco: Monaco, reason: string): void {
  const picked = pickEditor(monaco);
  const model = picked?.model ?? pickModel(monaco);

  if (!model) {
    console.log(`${LOG} no editor model yet (${reason})`);
    return;
  }

  const editorCount = monaco.editor.getEditors?.().length ?? -1;
  const message: CodeMessage = {
    source: BRIDGE_SOURCE,
    type: "code",
    code: model.getValue(),
    language: model.getLanguageId(),
    detail:
      `${picked ? "visible editor" : "model fallback"}; editors=${editorCount}, ` +
      `models=${monaco.editor.getModels().length}, uri=${model.uri.toString()}, reason=${reason}`,
  };

  // Same-origin target: only windows on leetcode.com can receive this, and the
  // isolated-world content script is listening on this very window.
  window.postMessage(message, location.origin);
}

let debounce: number | undefined;

function schedulePublish(monaco: Monaco, reason: string): void {
  clearTimeout(debounce);
  debounce = window.setTimeout(() => publish(monaco, reason), DEBOUNCE_MS);
}

// ---------------------------------------------------------------------------
// Following editors as they come and go
// ---------------------------------------------------------------------------

const attached = new WeakSet<Editor>();

/** Publish on every content change of whatever model this editor shows,
 *  re-subscribing when LeetCode swaps the model (language change, next problem). */
function attach(monaco: Monaco, editor: Editor): void {
  if (attached.has(editor)) return;
  attached.add(editor);

  let content: Disposable | null = null;

  const follow = () => {
    content?.dispose();
    const model = editor.getModel();
    content = model ? model.onDidChangeContent(() => schedulePublish(monaco, "edit")) : null;
    schedulePublish(monaco, "model");
  };

  follow();
  const modelSub = editor.onDidChangeModel(follow);

  editor.onDidDispose(() => {
    content?.dispose();
    modelSub.dispose();
    attached.delete(editor);
  });
}

/** Resolves when window.monaco exists. Polls forever rather than timing out:
 *  the script is injected on every leetcode.com page, and Monaco only loads
 *  once the user reaches a problem — which may be minutes later. */
function waitForMonaco(): Promise<Monaco> {
  return new Promise((resolve) => {
    const check = () => {
      if (window.monaco?.editor) {
        clearInterval(timer);
        resolve(window.monaco);
      }
    };
    const timer = setInterval(check, MONACO_POLL_MS);
    check();
  });
}

async function main(): Promise<void> {
  const monaco = await waitForMonaco();
  const hasEditorApi = typeof monaco.editor.getEditors === "function";
  console.log(`${LOG} monaco found (editor API: ${hasEditorApi ? "yes" : "no — models only"})`);

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data as Partial<CodeRequest> | null;
    if (data?.source === BRIDGE_SOURCE && data.type === "get-code") publish(monaco, "request");
  });

  if (hasEditorApi) {
    for (const editor of monaco.editor.getEditors!()) attach(monaco, editor);
    monaco.editor.onDidCreateEditor?.((editor) => attach(monaco, editor));
  } else {
    // No editor API: at least follow every model as it is created.
    for (const model of monaco.editor.getModels()) {
      model.onDidChangeContent(() => schedulePublish(monaco, "edit"));
    }
    monaco.editor.onDidCreateModel((model) => {
      model.onDidChangeContent(() => schedulePublish(monaco, "edit"));
      schedulePublish(monaco, "model");
    });
  }

  publish(monaco, "init");
}

void main();
