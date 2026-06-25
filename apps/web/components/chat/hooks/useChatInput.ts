import { useState, useRef, useEffect, useCallback } from "react";
import { CHAT_LIMITS } from "../constants";

export function useChatInput(onSubmit: (text: string) => void, isStreaming: boolean) {
  const [question, setQuestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea height
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to compute scroll height accurately
    textarea.style.height = "auto";
    const scrollHeight = textarea.scrollHeight;
    
    // Bounds height between 44px (1 line) and 150px (approx 6 lines)
    const newHeight = Math.max(44, Math.min(scrollHeight, 150));
    textarea.style.height = `${newHeight}px`;

    // Manage scrollbar visibility
    if (scrollHeight > 150) {
      textarea.style.overflowY = "auto";
    } else {
      textarea.style.overflowY = "hidden";
    }
  }, [question]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (question.trim() && !isStreaming) {
          onSubmit(question);
          setQuestion("");
        }
      }
    },
    [question, isStreaming, onSubmit]
  );

  return {
    question,
    setQuestion,
    textareaRef,
    handleKeyDown,
  };
}
