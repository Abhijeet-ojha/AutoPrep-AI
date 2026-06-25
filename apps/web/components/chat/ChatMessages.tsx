import React from "react";
import { AlertCircle, RotateCcw, ArrowDown } from "lucide-react";
import { Message, StreamStatus } from "./types";
import { ChatBubble } from "./ChatBubble";
import { ChatStatus } from "./ChatStatus";

interface ChatMessagesProps {
  messages: Message[];
  isStreaming: boolean;
  activePhase: StreamStatus;
  streamError: string | null;
  searchQuery: string;
  matchIndices: number[];
  currentMatchIdx: number;
  scrollContainerRef: React.RefObject<HTMLDivElement>;
  showScrollDownCta: boolean;
  onScroll: () => void;
  forceScrollToBottom: () => void;
  onEdit: (messageId: string) => void;
  onRegenerate: () => void;
}

export const ChatMessages: React.FC<ChatMessagesProps> = React.memo(({
  messages,
  isStreaming,
  activePhase,
  streamError,
  searchQuery,
  matchIndices,
  currentMatchIdx,
  scrollContainerRef,
  showScrollDownCta,
  onScroll,
  forceScrollToBottom,
  onEdit,
  onRegenerate,
}) => {
  // Find last assistant message index to pass isLastAssistantMessage
  const lastAssistantIdx = React.useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  }, [messages]);

  // Determine if a message bubble matches the currently focused search term
  const getIsActiveMatch = (msgIdx: number) => {
    if (matchIndices.length === 0) return false;
    return matchIndices[currentMatchIdx] === msgIdx;
  };

  return (
    <div className="relative flex-1 min-h-0">
      {/* Scrollable Container */}
      <div
        ref={scrollContainerRef}
        onScroll={onScroll}
        className="h-full overflow-y-auto p-4 space-y-4 scrollbar-thin"
      >
        {messages.map((msg, idx) => (
          <ChatBubble
            key={msg.id || idx}
            msg={msg}
            isGenerating={isStreaming && idx === messages.length - 1 && msg.role === "assistant"}
            searchQuery={searchQuery}
            isActiveMatch={getIsActiveMatch(idx)}
            onEdit={onEdit}
            onRegenerate={onRegenerate}
            isLastAssistantMessage={idx === lastAssistantIdx}
          />
        ))}

        {/* Phase-based status indicator */}
        {activePhase && <ChatStatus status={activePhase} />}

        {/* Resilience error alert with retry option */}
        {streamError && (
          <div className="flex flex-col gap-2 p-3.5 bg-red-50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/30 rounded-xl max-w-[90%] mx-auto text-xs font-semibold text-red-600 dark:text-red-400 animate-slide-up">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p>Connection interrupted.</p>
                <p className="text-[10px] text-slate-400 dark:text-zinc-500 font-medium mt-0.5">{streamError}</p>
              </div>
            </div>
            <div className="flex justify-end mt-1">
              <button
                type="button"
                onClick={onRegenerate}
                className="flex items-center gap-1.5 px-3 py-1 bg-red-100 hover:bg-red-200 dark:bg-red-900/40 dark:hover:bg-red-900/60 text-red-700 dark:text-red-300 rounded-lg text-[11px] transition-all font-bold active:scale-95"
              >
                <RotateCcw className="h-3 w-3" />
                Retry generation
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Floating Scroll-Down CTA */}
      {showScrollDownCta && (
        <button
          type="button"
          onClick={forceScrollToBottom}
          className="absolute bottom-4 right-4 flex items-center gap-1 px-3 py-1.5 bg-slate-900/90 hover:bg-slate-900 dark:bg-zinc-100/90 dark:hover:bg-zinc-100 text-white dark:text-zinc-950 rounded-full text-[11px] font-bold shadow-lg backdrop-blur-sm z-10 transition-all scale-100 hover:scale-105 active:scale-95 animate-bounce"
        >
          <ArrowDown className="h-3.5 w-3.5" />
          New response
        </button>
      )}
    </div>
  );
});

ChatMessages.displayName = "ChatMessages";
