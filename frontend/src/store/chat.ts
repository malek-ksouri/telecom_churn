/**
 * Conversation avec l'assistant, partagée entre la page Assistant et le panneau latéral :
 * la même conversation suit l'utilisateur sur toutes les pages.
 */
import { create } from "zustand";

import { type ChatTurn, streamChat } from "../api/chat";

export interface ToolTrace {
  name: string;
  args: Record<string, unknown>;
  durationMs: number | null;
  ok: boolean | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "streaming" | "done" | "error";
  tools: ToolTrace[];
  warnings: string[];
  provider: string | null;
  /** Bascule en mode démonstration pendant la réponse (quota, clé, délai…). */
  notice: string | null;
  error: string | null;
  /** Question à l'origine de la réponse (pour « Réessayer »). */
  question?: string;
}

const MAX_HISTORY = 10;

interface ChatState {
  messages: Message[];
  busy: boolean;
  panelOpen: boolean;
  controller: AbortController | null;
  send: (question: string) => Promise<void>;
  stop: () => void;
  reset: () => void;
  setPanelOpen: (open: boolean) => void;
}

let counter = 0;
const newId = () => `m${String(Date.now())}-${String(++counter)}`;

export const useChatStore = create<ChatState>((set, get) => {
  const patch = (id: string, update: (m: Message) => Partial<Message>) => {
    set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, ...update(m) } : m)) }));
  };

  return {
    messages: [],
    busy: false,
    panelOpen: false,
    controller: null,

    send: async (question) => {
      const text = question.trim();
      if (!text || get().busy) return;
      // Historique : 10 derniers messages terminés (l'API n'en garde pas davantage).
      const history: ChatTurn[] = get()
        .messages.filter((m) => m.status === "done" && m.content)
        .slice(-MAX_HISTORY)
        .map((m) => ({ role: m.role, content: m.content }));
      const userMsg: Message = {
        id: newId(), role: "user", content: text, status: "done", tools: [], warnings: [],
        provider: null, notice: null, error: null,
      };
      const answerId = newId();
      const answer: Message = {
        id: answerId, role: "assistant", content: "", status: "streaming", tools: [], warnings: [],
        provider: null, notice: null, error: null, question: text,
      };
      const controller = new AbortController();
      set((s) => ({ messages: [...s.messages, userMsg, answer], busy: true, controller }));
      try {
        await streamChat(text, history, {
          onToken: (token) => {
            patch(answerId, (m) => ({ content: m.content + token }));
          },
          onToolCall: (e) => {
            patch(answerId, (m) => ({ tools: [...m.tools, { name: e.name, args: e.args, durationMs: null, ok: null }] }));
          },
          onToolResult: (e) => {
            patch(answerId, (m) => {
              const tools = [...m.tools];
              const i = tools.findIndex((t) => t.name === e.name && t.durationMs === null);
              if (i >= 0) tools[i] = { name: e.name, args: e.args, durationMs: e.duration_ms, ok: e.ok };
              return { tools };
            });
          },
          onError: (e) => {
            if (e.recoverable) {
              // La réponse repart en mode démonstration : on efface le texte partiel.
              patch(answerId, () => ({ notice: e.message, content: "", tools: [] }));
            } else {
              patch(answerId, () => ({ status: "error", error: e.message }));
            }
          },
          onDone: (e) => {
            patch(answerId, () => ({
              status: "done",
              content: e.answer,
              tools: e.tool_calls.map((t) => ({ name: t.name, args: t.args, durationMs: t.duration_ms, ok: t.ok })),
              warnings: e.warnings,
              provider: e.provider,
            }));
          },
        }, controller.signal);
      } catch (error) {
        const aborted = error instanceof DOMException && error.name === "AbortError";
        patch(answerId, (m) => ({
          status: aborted && m.content ? "done" : "error",
          error: aborted ? "Réponse interrompue." : error instanceof Error ? error.message : "Erreur inattendue.",
        }));
      } finally {
        patch(answerId, (m) => (m.status === "streaming" ? { status: "error", error: "Réponse incomplète." } : {}));
        set({ busy: false, controller: null });
      }
    },

    stop: () => {
      get().controller?.abort();
    },

    reset: () => {
      get().controller?.abort();
      set({ messages: [], busy: false, controller: null });
    },

    setPanelOpen: (open) => {
      set({ panelOpen: open });
    },
  };
});
