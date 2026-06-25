import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { User, Bot, Copy, Check } from "lucide-react";
import { Message } from "./types";
import { getSearchMatchParts } from "./utils/search";
import { ChatToolbar } from "./ChatToolbar";

interface ChatBubbleProps {
  msg: Message;
  isGenerating: boolean;
  searchQuery: string;
  isActiveMatch: boolean;
  onEdit: (messageId: string) => void;
  onRegenerate: () => void;
  isLastAssistantMessage: boolean;
}

export const ChatBubble: React.FC<ChatBubbleProps> = React.memo(
  ({ msg, isGenerating, searchQuery, isActiveMatch, onEdit, onRegenerate, isLastAssistantMessage }) => {
    const [copied, setCopied] = useState(false);
    const bubbleRef = useRef<HTMLDivElement | null>(null);

    const handleCopy = () => {
      navigator.clipboard.writeText(msg.message);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    // Scroll into view if this is the active search match
    useEffect(() => {
      if (isActiveMatch && bubbleRef.current) {
        bubbleRef.current.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }
    }, [isActiveMatch]);

    // Helper component to highlight matches
    const HighlightText: React.FC<{ text: string }> = ({ text }) => {
      if (!searchQuery.trim()) return <>{text}</>;
      const parts = getSearchMatchParts(text, searchQuery);
      return (
        <>
          {parts.map((part, i) => {
            const isMatch = part.toLowerCase() === searchQuery.toLowerCase();
            return isMatch ? (
              <mark
                key={i}
                className={`px-0.5 rounded transition-all duration-200 ${
                  isActiveMatch
                    ? "bg-amber-300 dark:bg-amber-750 text-slate-950 dark:text-white ring-1 ring-amber-500 font-bold"
                    : "bg-yellow-200/90 dark:bg-yellow-950/50 text-slate-900 dark:text-zinc-100 font-medium"
                }`}
              >
                {part}
              </mark>
            ) : (
              part
            );
          })}
        </>
      );
    };

    return (
      <div
        ref={bubbleRef}
        className={`flex items-start gap-3 max-w-[90%] animate-slide-up transition-all duration-300 ${
          msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto w-full"
        } ${isActiveMatch ? "ring-2 ring-amber-400/50 rounded-2xl p-1" : ""}`}
      >
        <div
          className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm ${
            msg.role === "user"
              ? "bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
              : "bg-red-500 text-white"
          }`}
        >
          {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </div>

        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm relative group transition-all duration-300 ${
            msg.role === "user"
              ? "bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900 rounded-tr-none"
              : "bg-white text-slate-800 dark:bg-zinc-800 dark:text-zinc-100 border border-slate-100 dark:border-zinc-750 rounded-tl-none w-full overflow-hidden"
          }`}
        >
          {msg.role === "assistant" ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  table: ({ node, ...props }) => (
                    <div className="overflow-x-auto my-3 w-full border border-slate-200 dark:border-zinc-800 rounded-lg shadow-sm">
                      <table className="min-w-full divide-y divide-slate-200 dark:divide-zinc-700" {...props} />
                    </div>
                  ),
                  thead: ({ node, ...props }) => <thead className="bg-slate-50 dark:bg-zinc-800/60" {...props} />,
                  tbody: ({ node, ...props }) => <tbody className="divide-y divide-slate-100 dark:divide-zinc-800" {...props} />,
                  tr: ({ node, ...props }) => (
                    <tr
                      className="even:bg-slate-50/40 dark:even:bg-zinc-800/10 hover:bg-slate-100/30 dark:hover:bg-zinc-750/30 transition-colors"
                      {...props}
                    />
                  ),
                  th: ({ node, ...props }) => (
                    <th
                      className="px-3.5 py-2 text-left text-xs font-semibold text-slate-600 dark:text-zinc-300 uppercase tracking-wider"
                      {...props}
                    />
                  ),
                  td: ({ node, ...props }) => (
                    <td className="px-3.5 py-2 text-xs text-slate-600 dark:text-zinc-400 whitespace-normal break-words" {...props} />
                  ),
                  h1: ({ node, children }) => (
                    <h1 className="text-sm font-bold text-slate-900 dark:text-zinc-100 mt-3 mb-1.5 first:mt-0">
                      {typeof children === "string" ? <HighlightText text={children} /> : children}
                    </h1>
                  ),
                  h2: ({ node, children }) => (
                    <h2 className="text-xs font-bold text-slate-900 dark:text-zinc-100 mt-2.5 mb-1">
                      {typeof children === "string" ? <HighlightText text={children} /> : children}
                    </h2>
                  ),
                  h3: ({ node, children }) => (
                    <h3 className="text-[11px] font-bold text-slate-900 dark:text-zinc-100 mt-2 mb-1">
                      {typeof children === "string" ? <HighlightText text={children} /> : children}
                    </h3>
                  ),
                  p: ({ node, children }) => (
                    <p className="mb-2 last:mb-0 leading-relaxed text-xs">
                      {typeof children === "string" ? <HighlightText text={children} /> : children}
                    </p>
                  ),
                  li: ({ node, children }) => (
                    <li className="leading-relaxed">
                      {typeof children === "string" ? <HighlightText text={children} /> : children}
                    </li>
                  ),
                  ul: ({ node, ...props }) => <ul className="list-disc pl-4 mb-2 space-y-1 text-xs" {...props} />,
                  ol: ({ node, ...props }) => <ol className="list-decimal pl-4 mb-2 space-y-1 text-xs" {...props} />,
                  blockquote: ({ node, ...props }) => (
                    <blockquote className="border-l-4 border-red-500/80 pl-3 py-1 italic text-slate-500 dark:text-zinc-400 my-2.5 bg-slate-50/50 dark:bg-zinc-850/30 rounded-r-lg" {...props} />
                  ),
                  code: ({ node, inline, className, children, ...props }: any) => {
                    const match = /language-(\w+)/.exec(className || "");
                    const [codeCopied, setCodeCopied] = React.useState(false);
                    const codeString = String(children).replace(/\n$/, "");

                    const handleCodeCopy = () => {
                      navigator.clipboard.writeText(codeString);
                      setCodeCopied(true);
                      setTimeout(() => setCodeCopied(false), 2000);
                    };

                    return !inline ? (
                      <div className="relative group/code my-2.5 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-950">
                        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-100 dark:bg-zinc-900 border-b border-slate-200 dark:border-zinc-800 text-[10px] font-mono text-slate-500 dark:text-zinc-400">
                          <span>{match ? match[1] : "code"}</span>
                          <button
                            type="button"
                            onClick={handleCodeCopy}
                            className="p-1 hover:bg-slate-200 dark:hover:bg-zinc-800 rounded transition-all"
                          >
                            {codeCopied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                          </button>
                        </div>
                        <pre className="p-3 text-[11px] font-mono overflow-x-auto leading-relaxed text-slate-800 dark:text-zinc-200">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      </div>
                    ) : (
                      <code
                        className="bg-slate-100 dark:bg-zinc-850 px-1 py-0.5 rounded text-[11px] font-mono text-slate-850 dark:text-zinc-200"
                        {...props}
                      >
                        {typeof children === "string" ? <HighlightText text={children} /> : children}
                      </code>
                    );
                  },
                }}
              >
                {msg.message}
              </ReactMarkdown>
            </div>
          ) : (
            <p className="text-xs">
              <HighlightText text={msg.message} />
            </p>
          )}

          {isGenerating && (
            <span className="inline-block w-1.5 h-4 bg-red-500 dark:bg-red-400 ml-1 animate-cursor-blink align-middle" />
          )}

          {/* Action Toolbar (Desktop Hover / Mobile Bottom Sheet) */}
          <ChatToolbar
            role={msg.role}
            copied={copied}
            onCopy={handleCopy}
            onEdit={() => onEdit(msg.id)}
            onRegenerate={onRegenerate}
            isLastAssistantMessage={isLastAssistantMessage}
            isGenerating={isGenerating}
          />

          {/* Assistant message footer metadata */}
          {msg.role === "assistant" && (
            <div className="flex flex-col mt-2">
              {/* Metadata block */}
              {msg.metadata && (msg.metadata.model_used || msg.metadata.latency_ms || msg.metadata.generation_time) && (
                <div className="text-[10px] text-slate-400 dark:text-zinc-500 font-medium flex flex-wrap gap-x-2.5 gap-y-1 items-center border-t border-slate-100 dark:border-zinc-800/60 pt-1.5 select-none">
                  {msg.metadata.model_used && (
                    <span>
                      Model: <span className="font-semibold text-slate-500 dark:text-zinc-400">{msg.metadata.model_used}</span>
                    </span>
                  )}
                  {msg.metadata.provider_used && (
                    <span>
                      Provider: <span className="font-semibold text-slate-500 dark:text-zinc-400">{msg.metadata.provider_used}</span>
                    </span>
                  )}
                  {(msg.metadata.latency_ms || msg.metadata.generation_time) && (
                    <span>
                      Time: <span className="font-semibold text-slate-500 dark:text-zinc-400">
                        {((msg.metadata.latency_ms || msg.metadata.generation_time) / 1000).toFixed(2)}s
                      </span>
                    </span>
                  )}
                  {msg.metadata.response_length !== undefined && (
                    <span>
                      Length: <span className="font-semibold text-slate-500 dark:text-zinc-400">{msg.metadata.response_length} chars</span>
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    return (
      prevProps.msg.message === nextProps.msg.message &&
      prevProps.isGenerating === nextProps.isGenerating &&
      prevProps.searchQuery === nextProps.searchQuery &&
      prevProps.isActiveMatch === nextProps.isActiveMatch &&
      prevProps.isLastAssistantMessage === nextProps.isLastAssistantMessage
    );
  }
);

ChatBubble.displayName = "ChatBubble";
