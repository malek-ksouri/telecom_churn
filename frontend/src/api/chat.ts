/**
 * Client du chat en streaming (Server-Sent Events sur POST /api/chat).
 *
 * `EventSource` ne permet pas de POST : on lit le corps de la réponse en flux et on découpe
 * les événements (« event: … » / « data: … », séparés par une ligne vide).
 */
import { API_BASE, ApiError, apiPost } from "./client";
import type { components } from "./schema";

export type ChatAnswer = components["schemas"]["ChatAnswer"];
export type AdvisorExplanation = components["schemas"]["AdvisorExplanation"];
export type RetentionMessage = components["schemas"]["RetentionMessage"];

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ToolCallEvent {
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResultEvent extends ToolCallEvent {
  duration_ms: number;
  ok: boolean;
}

export interface ChatErrorEvent {
  message: string;
  kind: string;
  recoverable: boolean;
  fallback?: string;
}

export interface ChatHandlers {
  onToken: (text: string, step: number) => void;
  onToolCall: (e: ToolCallEvent) => void;
  onToolResult: (e: ToolResultEvent) => void;
  onError: (e: ChatErrorEvent) => void;
  onDone: (e: ChatAnswer) => void;
}

function dispatch(block: string, handlers: ChatHandlers): void {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return;
  const payload: unknown = JSON.parse(data.join("\n"));
  switch (event) {
    case "token": {
      const p = payload as { text: string; step: number };
      handlers.onToken(p.text, p.step);
      break;
    }
    case "tool_call":
      handlers.onToolCall(payload as ToolCallEvent);
      break;
    case "tool_result":
      handlers.onToolResult(payload as ToolResultEvent);
      break;
    case "error":
      handlers.onError(payload as ChatErrorEvent);
      break;
    case "done":
      handlers.onDone(payload as ChatAnswer);
      break;
    default:
      break;
  }
}

/** Envoie une question et relaie les événements au fil de l'eau. */
export async function streamChat(
  message: string,
  history: ChatTurn[],
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ message, history }),
      signal: signal ?? null,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "API injoignable : vérifiez que le serveur est lancé.");
  }
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, response.status === 422 ? "Question invalide (vide ou trop longue)." : "L'assistant n'a pas pu répondre.");
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      dispatch(buffer.slice(0, index), handlers);
      buffer = buffer.slice(index + 2);
      index = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer, handlers);
}

export function explainCustomerAi(id: number): Promise<AdvisorExplanation> {
  return apiPost<AdvisorExplanation>(`${API_BASE}/customers/${String(id)}/explain-ai`);
}

export function retentionMessageAi(id: number): Promise<RetentionMessage> {
  return apiPost<RetentionMessage>(`${API_BASE}/customers/${String(id)}/retention-message`);
}
