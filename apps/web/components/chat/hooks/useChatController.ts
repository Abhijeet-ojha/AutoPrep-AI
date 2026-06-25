import { useState, useCallback, useMemo, useEffect } from "react";
import { Message } from "../types";
import { useChatStreaming } from "./useChatStreaming";
import { useChatSearch } from "./useChatSearch";
import { useChatSuggestions } from "./useChatSuggestions";
import { useChatExport } from "./useChatExport";
import { useChatScroll } from "./useChatScroll";
import { useChatFullscreen } from "./useChatFullscreen";
import { useChatInput } from "./useChatInput";

export function useChatController(datasetId: string, initialHistory: Message[] = []) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([
    "Explain dataset quality",
    "Is this dataset ready for machine learning?",
    "What cleaning actions were applied?",
    "What model should I use?",
    "What are the most important features?"
  ]);

  // Sync initial history
  useEffect(() => {
    if (initialHistory && initialHistory.length > 0) {
      setMessages(initialHistory);
    } else {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          message: "Hello! I am your Dataset Copilot. I've analyzed your data and cleaned duplicate rows, handled missing values, and calculated statistical summaries. Ask me anything about the data or choose from one of the quick start questions below!"
        }
      ]);
    }
  }, [initialHistory, datasetId]);

  // Initialize individual hooks
  const {
    isStreaming,
    activePhase,
    streamError,
    startStreaming,
    stopStreaming,
  } = useChatStreaming(datasetId, setMessages, setSuggestedQuestions);

  const {
    searchQuery,
    setSearchQuery,
    showSearch,
    setShowSearch,
    currentMatchIdx,
    matchIndices,
    nextMatch,
    prevMatch,
    clearSearch,
    searchInputRef,
  } = useChatSearch(messages);

  const {
    chips,
    visible: suggestionsVisible,
  } = useChatSuggestions(suggestedQuestions);

  const {
    exportMarkdown,
    exportPDF,
    isExporting,
  } = useChatExport(datasetId, messages);

  const {
    scrollContainerRef,
    showScrollDownCta,
    handleScroll,
    forceScrollToBottom,
  } = useChatScroll(messages, isStreaming);

  const askCopilot = useCallback((text: string) => {
    if (!text.trim() || isStreaming) return;
    startStreaming(text, false);
  }, [isStreaming, startStreaming]);

  const editPrompt = useCallback((messageId: string) => {
    // Find index of the edited message in message list
    const idx = messages.findIndex(m => m.id === messageId);
    if (idx === -1) return "";

    const originalText = messages[idx].message;
    
    // Prune history from this index onwards (and recreate new branch)
    setMessages(prev => prev.slice(0, idx));
    
    return originalText; // return to populate input field
  }, [messages]);

  const regenerateLastResponse = useCallback(() => {
    if (isStreaming) return;
    
    // Find last user prompt
    const userIndices = messages
      .map((m, i) => (m.role === "user" ? i : -1))
      .filter((i) => i !== -1);

    if (userIndices.length === 0) return;
    const lastUserIdx = userIndices[userIndices.length - 1];
    const lastUserPrompt = messages[lastUserIdx].message;

    // Trigger streaming with isRegenerate = true, which will swap 
    // the old response once the first token arrives
    startStreaming(lastUserPrompt, true);
  }, [messages, isStreaming, startStreaming]);

  const {
    question,
    setQuestion,
    textareaRef,
    handleKeyDown,
  } = useChatInput(askCopilot, isStreaming);

  const {
    isExpanded,
    mounted,
    modalContainerRef,
    openFullscreen,
    closeFullscreen,
  } = useChatFullscreen();

  return {
    // State
    messages,
    isStreaming,
    activePhase,
    streamError,
    suggestedQuestions: chips,
    suggestionsVisible,
    searchQuery,
    setSearchQuery,
    showSearch,
    setShowSearch,
    currentMatchIdx,
    matchIndices,
    isExporting,
    showScrollDownCta,
    isExpanded,
    mounted,
    question,
    setQuestion,

    // Refs
    scrollContainerRef,
    searchInputRef,
    textareaRef,
    modalContainerRef,

    // Callbacks
    askCopilot,
    stopStreaming,
    editPrompt,
    regenerateLastResponse,
    exportMarkdown,
    exportPDF,
    handleScroll,
    forceScrollToBottom,
    openFullscreen,
    closeFullscreen,
    handleKeyDown,
    nextMatch,
    prevMatch,
    clearSearch,
  };
}
export type ChatController = ReturnType<typeof useChatController>;
