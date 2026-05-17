"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
};

type MessageBubbleProps = {
  message: ChatMessage;
};

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={[
          "max-w-[88%] rounded-2xl px-4 py-3 text-[15px] leading-7 shadow-sm sm:max-w-[74%]",
          isUser
            ? "rounded-br-md bg-indigo-600 text-white"
            : "rounded-bl-md border border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100",
        ].join(" ")}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : message.streaming && !message.content ? (
          <div className="flex h-7 items-center gap-1.5" aria-label="Assistant is typing">
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-zinc-500 dark:bg-zinc-400" />
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-zinc-500 dark:bg-zinc-400" />
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-zinc-500 dark:bg-zinc-400" />
          </div>
        ) : (
          <div className="break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ children, ...props }) => (
                  <a
                    className="font-medium text-indigo-600 underline underline-offset-2 dark:text-indigo-400"
                    target="_blank"
                    rel="noreferrer"
                    {...props}
                  >
                    {children}
                  </a>
                ),
                code: ({ children, className, ...props }) => (
                  <code
                    className={[
                      "rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[0.9em] dark:bg-zinc-800",
                      className,
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    {...props}
                  >
                    {children}
                  </code>
                ),
                li: ({ children, ...props }) => (
                  <li className="ml-5 list-disc" {...props}>
                    {children}
                  </li>
                ),
                ol: ({ children, ...props }) => (
                  <ol className="my-3 space-y-1" {...props}>
                    {children}
                  </ol>
                ),
                p: ({ children, ...props }) => (
                  <p className="mb-3 last:mb-0" {...props}>
                    {children}
                  </p>
                ),
                pre: ({ children, ...props }) => (
                  <pre
                    className="my-3 overflow-x-auto rounded-lg bg-zinc-950 p-3 text-sm text-zinc-50"
                    {...props}
                  >
                    {children}
                  </pre>
                ),
                ul: ({ children, ...props }) => (
                  <ul className="my-3 space-y-1" {...props}>
                    {children}
                  </ul>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
            {message.streaming ? (
              <span className="stream-cursor ml-0.5 inline-block text-indigo-500">
                ▍
              </span>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
