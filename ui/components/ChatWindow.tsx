"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import MemoryPanel from "./MemoryPanel";
import MessageBubble, { ChatMessage } from "./MessageBubble";

function decodeSseData(rawData: string) {
  if (rawData === "[DONE]") {
    return rawData;
  }

  try {
    return JSON.parse(rawData) as string;
  } catch {
    return rawData;
  }
}

function extractErrorMessage(payload: unknown) {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  if (
    payload &&
    typeof payload === "object" &&
    "error" in payload &&
    typeof payload.error === "string"
  ) {
    return payload.error;
  }
  return null;
}

function hasStreamError(payload: unknown): payload is { error: string } {
  return (
    !!payload &&
    typeof payload === "object" &&
    "error" in payload &&
    typeof (payload as { error?: unknown }).error === "string"
  );
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`;
  }, [draft]);

  function updateStreamingAssistant(
    updater: (message: ChatMessage) => ChatMessage,
  ) {
    setMessages((current) => {
      const next = [...current];
      for (let index = next.length - 1; index >= 0; index -= 1) {
        if (next[index].role === "assistant" && next[index].streaming) {
          next[index] = updater(next[index]);
          return next;
        }
      }
      return current;
    });
  }

  async function sendMessage(text: string) {
    const content = text.trim();
    if (!content || isSending) {
      return;
    }

    setDraft("");
    setIsSending(true);
    setMessages((current) => [
      ...current,
      { role: "user", content },
      { role: "assistant", content: "", streaming: true },
    ]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content }),
      });

      if (!response.ok) {
        let message = "Chat request failed";
        try {
          const payload = (await response.json()) as unknown;
          message = extractErrorMessage(payload) ?? message;
        } catch {
          message = response.statusText || message;
        }
        throw new Error(message);
      }

      if (!response.body) {
        throw new Error("The AI backend did not return a stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let doneStreaming = false;

      while (!doneStreaming) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const event of events) {
          const dataLines = event
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) =>
              line.startsWith("data: ") ? line.slice(6) : line.slice(5),
            );
          if (dataLines.length === 0) {
            continue;
          }

          const data = dataLines.join("\n");
          if (data === "[DONE]") {
            updateStreamingAssistant((message) => ({
              ...message,
              streaming: false,
            }));
            doneStreaming = true;
            break;
          }

          const token = decodeSseData(data);
          if (hasStreamError(token)) {
            throw new Error(token.error);
          }
          updateStreamingAssistant((message) => ({
            ...message,
            content: `${message.content}${token}`,
          }));
        }
      }

      updateStreamingAssistant((message) => ({ ...message, streaming: false }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      updateStreamingAssistant(() => ({
        role: "assistant",
        content: `I could not complete that request: ${message}`,
        streaming: false,
      }));
    } finally {
      setIsSending(false);
    }
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(draft);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(draft);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="text-base font-semibold tracking-tight">
            Personal AI
          </Link>
          <nav className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMemoryOpen(true)}
              className="hidden rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900 sm:inline-flex"
            >
              Memory
            </button>
            <Link
              href="/memory"
              className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              Manage
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <div className="flex min-h-[55dvh] items-center justify-center px-2 text-center">
              <div className="w-full max-w-sm">
                <h1 className="text-balance text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
                  What are we thinking through?
                </h1>
                <p className="mt-3 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
                  Your private assistant streams replies here and keeps its memory on the backend.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => (
                <MessageBubble key={`${message.role}-${index}`} message={message} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form
          onSubmit={submitMessage}
          className="sticky bottom-0 border-t border-zinc-200 bg-zinc-50/95 px-4 py-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/95 sm:px-6"
        >
          <div className="flex min-w-0 items-end gap-2 rounded-2xl border border-zinc-300 bg-white p-2 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Message your AI..."
              className="max-h-36 min-h-11 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-3 py-2 text-[15px] leading-6 outline-none placeholder:text-zinc-400"
            />
            <button
              type="submit"
              disabled={isSending || !draft.trim()}
              className="min-h-11 flex-none rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 dark:disabled:bg-zinc-800"
            >
              Send
            </button>
          </div>
        </form>
      </main>

      <MemoryPanel
        open={memoryOpen}
        onClose={() => setMemoryOpen(false)}
      />
    </div>
  );
}
