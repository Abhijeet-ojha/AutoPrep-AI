import React from "react";
import { Send, Square } from "lucide-react";

interface ChatInputProps {
  question: string;
  setQuestion: (q: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (e: React.FormEvent) => void;
  isStreaming: boolean;
  onStop: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = React.memo(({
  question,
  setQuestion,
  textareaRef,
  onKeyDown,
  onSubmit,
  isStreaming,
  onStop,
}) => {
  const handleSubmitForm = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(e);
  };

  return (
    <form
      onSubmit={handleSubmitForm}
      className="p-3 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex gap-2 items-end shrink-0"
    >
      <div className="relative flex-1 flex items-center bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl overflow-hidden focus-within:ring-1 focus-within:ring-slate-400 focus-within:border-slate-400 transition-all">
        <textarea
          ref={textareaRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder={
            isStreaming
              ? "Generating response..."
              : "Ask Copilot about your dataset quality, outliers, or modeling ideas..."
          }
          disabled={isStreaming}
          className="flex-1 max-h-[150px] resize-none bg-transparent py-3 pl-4 pr-12 text-sm text-slate-800 dark:text-zinc-200 placeholder-slate-400 focus:outline-none disabled:opacity-75 leading-relaxed self-center scrollbar-thin"
          style={{ height: "44px", overflowY: "hidden" }}
        />
        
        {/* Absolute positioned action button inside input on the right */}
        <div className="absolute right-2 bottom-1.5">
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              title="Stop generation"
              className="h-8 w-8 rounded-lg bg-red-550 hover:bg-red-650 text-white flex items-center justify-center shadow transition-all active:scale-95"
            >
              <Square className="h-3.5 w-3.5 fill-white" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!question.trim()}
              title="Send message"
              className="h-8 w-8 rounded-lg bg-slate-900 hover:bg-slate-850 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-950 flex items-center justify-center shadow transition-all disabled:opacity-30 disabled:scale-100 active:scale-95"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </form>
  );
});

ChatInput.displayName = "ChatInput";
