/**
 * The extension's side of the backend contract (backend/app/schemas.py).
 */

import { supabase } from "./supabase";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

export type ChatTurn = { role: "user" | "assistant"; content: string };

export type ChatRequest = {
  messages: ChatTurn[];
  problem?: {
    slug: string;
    title?: string | null;
    difficulty?: string | null;
    statement?: string | null;
  };
  code?: {
    language: string | null;
    code: string;
  };
};

export type ChatResponse = {
  reply: string;
  model: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
    cache_read_input_tokens: number;
    cache_creation_input_tokens: number;
  };
};

export class BackendError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  if (!BACKEND_URL) {
    throw new Error("VITE_BACKEND_URL is not set — add it to extension/.env.local and rebuild.");
  }

  // getSession() hands back the stored session, refreshing the access token
  // first if it is about to expire — so this is always a token the backend
  // will accept, not whatever was current when the panel opened.
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new BackendError(401, "Not signed in");
  }

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(request),
    });
  } catch {
    throw new BackendError(0, `Can't reach the backend at ${BACKEND_URL}. Is it running?`);
  }

  if (!response.ok) {
    // FastAPI puts a human-readable reason in `detail` for errors we raise
    // ourselves; validation errors put a list there, which falls through to
    // the status text.
    let detail = response.statusText;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && typeof (body as { detail?: unknown }).detail === "string") {
        detail = (body as { detail: string }).detail;
      }
    } catch {
      // not JSON
    }
    throw new BackendError(response.status, detail);
  }

  return (await response.json()) as ChatResponse;
}
