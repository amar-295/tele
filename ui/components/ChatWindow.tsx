"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { BrainIcon, DatabaseIcon, SendIcon, SparkIcon } from "./Icons";
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
    <div className="relative flex min-h-dvh flex-col overflow-hidden bg-[radial-gradient(circle_at_top_left,#e0e7ff_0,transparent_28rem),linear-gradient(180deg,#fafafa,#f4f4f5)] dark:bg-[radial-gradient(circle_at_top_left,rgba(79,70,229,0.22)_0,transparent_30rem),linear-gradient(180deg,#08080a,#0b0b10)]">
      <header className="sticky top-0 z-20 border-b border-zinc-200/80 bg-white/75 shadow-sm shadow-zinc-950/5 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/70 dark:shadow-black/20">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-3 text-base font-semibold tracking-tight">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-zinc-950 text-white shadow-lg shadow-zinc-950/15 ring-1 ring-white/10 dark:bg-white dark:text-zinc-950">
              <SparkIcon className="h-4.5 w-4.5" />
            </span>
            <span>Personal AI</span>
          </Link>
          <nav className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMemoryOpen(true)}
              className="hidden items-center gap-2 rounded-xl border border-zinc-300/80 bg-white/70 px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm shadow-zinc-950/5 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:text-zinc-200 dark:hover:bg-white/10 sm:inline-flex"
            >
              <DatabaseIcon className="h-4 w-4" />
              Memory
            </button>
            <Link
              href="/memory"
              className="inline-flex items-center gap-2 rounded-xl bg-zinc-950 px-3 py-2 text-sm font-semibold text-white shadow-lg shadow-zinc-950/15 hover:bg-zinc-800 dark:bg-white dark:text-zinc-950 dark:hover:bg-zinc-200"
            >
              <BrainIcon className="h-4 w-4" />
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
                <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl border border-zinc-200 bg-white text-zinc-950 shadow-xl shadow-zinc-950/10 dark:border-white/10 dark:bg-white/10 dark:text-white">
                  <SparkIcon className="h-6 w-6" />
                </div>
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
          className="sticky bottom-0 border-t border-zinc-200/80 bg-zinc-50/80 px-4 py-3 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/80 sm:px-6"
        >
          <div className="flex min-w-0 items-end gap-2 rounded-2xl border border-zinc-300/80 bg-white/90 p-2 shadow-2xl shadow-zinc-950/10 ring-1 ring-white/80 dark:border-white/10 dark:bg-white/10 dark:shadow-black/30 dark:ring-white/5">
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
              className="grid min-h-11 w-11 flex-none place-items-center rounded-xl bg-zinc-950 text-white shadow-lg shadow-zinc-950/15 transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 dark:bg-white dark:text-zinc-950 dark:hover:bg-zinc-200 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-500"
              aria-label="Send message"
            >
              <SendIcon className="h-4.5 w-4.5" />
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
