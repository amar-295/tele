"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Stats = {
  messages_sent: number;
  replies_sent: number;
  message_count: number;
  fact_count: number;
  vector_facts: number;
  vector_conversations: number;
};

type MemoryPanelProps = {
  fullPage?: boolean;
  open?: boolean;
  onClose?: () => void;
};

const emptyStats: Stats = {
  messages_sent: 0,
  replies_sent: 0,
  message_count: 0,
  fact_count: 0,
  vector_facts: 0,
  vector_conversations: 0,
};

export default function MemoryPanel({
  fullPage = false,
  open = true,
  onClose,
}: MemoryPanelProps) {
  const [facts, setFacts] = useState<string[]>([]);
  const [stats, setStats] = useState<Stats>(emptyStats);
  const [newFact, setNewFact] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!open && !fullPage) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const [memoryResponse, statsResponse] = await Promise.all([
        fetch("/api/memory", { cache: "no-store" }),
        fetch("/api/stats", { cache: "no-store" }),
      ]);

      if (!memoryResponse.ok || !statsResponse.ok) {
        throw new Error("Unable to load memory");
      }

      const memoryJson = (await memoryResponse.json()) as { facts: string[] };
      const statsJson = (await statsResponse.json()) as Stats;
      setFacts(memoryJson.facts);
      setStats(statsJson);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load memory");
    } finally {
      setLoading(false);
    }
  }, [fullPage, open]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function addFact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fact = newFact.trim();
    if (!fact) {
      return;
    }

    setError("");
    const response = await fetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fact }),
    });

    if (!response.ok) {
      setError("Unable to add fact");
      return;
    }

    setNewFact("");
    await refresh();
  }

  async function deleteFact(fact: string) {
    const keyword = window.prompt(
      "Delete every fact and vector memory containing this keyword:",
      fact,
    );
    const cleanKeyword = keyword?.trim();
    if (!cleanKeyword) {
      return;
    }
    if (!window.confirm(`Delete memories matching "${cleanKeyword}"?`)) {
      return;
    }

    const response = await fetch(`/api/memory/${encodeURIComponent(cleanKeyword)}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      setError("Unable to delete matching memories");
      return;
    }
    await refresh();
  }

  async function clearHistory() {
    if (!window.confirm("Clear chat history? Stored facts will remain.")) {
      return;
    }

    const response = await fetch("/api/clear", { method: "POST" });
    if (!response.ok) {
      setError("Unable to clear history");
      return;
    }
    await refresh();
  }

  const statsItems = [
    ["Messages", stats.messages_sent],
    ["Replies", stats.replies_sent],
    ["History", stats.message_count],
    ["Facts", stats.fact_count],
    ["Vector facts", stats.vector_facts],
    ["Vector chats", stats.vector_conversations],
  ];

  const panel = (
    <section
      className={[
        "flex h-full flex-col bg-zinc-50 text-zinc-950 dark:bg-zinc-950 dark:text-zinc-50",
        fullPage ? "min-h-dvh" : "overflow-hidden",
      ].join(" ")}
    >
      <header className="flex min-h-16 items-center justify-between border-b border-zinc-200 px-4 dark:border-zinc-800 sm:px-6">
        <div>
          <h1 className="text-base font-semibold">Memory</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Facts and conversation counts
          </p>
        </div>
        {fullPage ? (
          <Link
            href="/"
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            Back to chat
          </Link>
        ) : (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            Close
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {statsItems.map(([label, value]) => (
            <div
              key={label}
              className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <p className="text-xs text-zinc-500 dark:text-zinc-400">{label}</p>
              <p className="mt-1 text-xl font-semibold">{value}</p>
            </div>
          ))}
        </div>

        <form onSubmit={addFact} className="mt-5 flex gap-2">
          <input
            value={newFact}
            onChange={(event) => setNewFact(event.target.value)}
            placeholder="Add a fact"
            className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none ring-indigo-500 transition focus:ring-2 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            type="submit"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Add
          </button>
        </form>

        <button
          type="button"
          onClick={clearHistory}
          className="mt-3 rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          Clear history
        </button>

        {error ? (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
            {error}
          </p>
        ) : null}

        <div className="mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Stored facts</h2>
            {loading ? (
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                Refreshing
              </span>
            ) : null}
          </div>
          {facts.length === 0 ? (
            <p className="rounded-lg border border-dashed border-zinc-300 p-4 text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
              No facts stored yet.
            </p>
          ) : (
            facts.map((fact) => (
              <div
                key={fact}
                className="flex gap-3 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <p className="min-w-0 flex-1 text-sm leading-6 text-zinc-700 dark:text-zinc-200">
                  {fact}
                </p>
                <button
                  type="button"
                  onClick={() => void deleteFact(fact)}
                  className="self-start rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/40"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );

  if (fullPage) {
    return panel;
  }

  return (
    <div
      className={[
        "fixed inset-0 z-40 bg-black/30 transition-opacity",
        open ? "opacity-100" : "pointer-events-none opacity-0",
      ].join(" ")}
      onClick={onClose}
    >
      <div
        className={[
          "absolute bottom-0 left-0 right-0 h-[82dvh] overflow-hidden rounded-t-2xl border border-zinc-200 bg-zinc-50 shadow-2xl transition-transform dark:border-zinc-800 dark:bg-zinc-950 md:bottom-0 md:left-auto md:top-0 md:h-full md:w-[420px] md:rounded-none md:rounded-l-2xl",
          open ? "translate-y-0 md:translate-x-0" : "translate-y-full md:translate-x-full md:translate-y-0",
        ].join(" ")}
        onClick={(event) => event.stopPropagation()}
      >
        {panel}
      </div>
    </div>
  );
}
