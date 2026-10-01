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
    /** Uncached input, billed at the full rate. */
    input_tokens: number;
    output_tokens: number;
    /** Part of output_tokens spent thinking. 0 for providers that don't report it. */
    reasoning_tokens: number;
    cache_read_input_tokens: number;
    cache_creation_input_tokens: number;
  };
  timing: {
    /** The model call alone. */
    model_ms: number;
    /** The whole backend route, including auth. */
    backend_ms: number;
  };
  /** Estimated; null when the backend has no price for the model. */
  cost_usd: number | null;
};

/** What the panel gets back: the response plus its own measurement of the
 *  full wait, from clicking send to having the reply. */
export type ChatResult = ChatResponse & { round_trip_ms: number };

export class BackendError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

/** An accepted submission, for the backend to summarise and store. */
export type SolutionRequest = {
  submission_id: number;
  problem: NonNullable<ChatRequest["problem"]>;
  problem_number: string | null;
  topic_tags: string[];
  language: string | null;
  code: string;
};

export type SolutionResponse = {
  summary: string;
  /** True when the backend already had this submission: nothing was written
   *  and no model call was made. */
  already_saved: boolean;
  model: string | null;
  cost_usd: number | null;
};

/** One authenticated POST to the backend. */
async function post<T>(path: string, body: unknown): Promise<T> {
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
    response = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(body),
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

  return (await response.json()) as T;
}

export async function sendChat(request: ChatRequest): Promise<ChatResult> {
  // Measured around the whole call so the token refresh inside post() counts
  // too — it is part of what the user waits for.
  const started = performance.now();
  const body = await post<ChatResponse>("/chat", request);
  return { ...body, round_trip_ms: Math.round(performance.now() - started) };
}

export function saveSolution(request: SolutionRequest): Promise<SolutionResponse> {
  return post<SolutionResponse>("/solutions", request);
}
