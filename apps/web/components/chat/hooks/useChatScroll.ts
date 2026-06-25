import { useState, useCallback, useRef, useEffect } from "react";
import { isNearBottomBoundary, scrollToBottom } from "../utils/scroll";

export function useChatScroll(messages: any[], isStreaming: boolean) {
  const [userIsNearBottom, setUserIsNearBottom] = useState(true);
  const [showScrollDownCta, setShowScrollDownCta] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const near = isNearBottomBoundary(container, 45);
    setUserIsNearBottom(near);

    // If streaming and not near bottom, show "New response ↓" trigger
    if (isStreaming && !near) {
      setShowScrollDownCta(true);
    } else if (near) {
      setShowScrollDownCta(false);
    }
  }, [isStreaming]);

  // Scroll to bottom manually
  const forceScrollToBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (container) {
      scrollToBottom(container, true);
      setUserIsNearBottom(true);
      setShowScrollDownCta(false);
    }
  }, []);

  // Automatically scroll to bottom during streaming ONLY IF user is already near bottom
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    if (isStreaming) {
      if (userIsNearBottom) {
        scrollToBottom(container, true);
        setShowScrollDownCta(false);
      } else {
        setShowScrollDownCta(true);
      }
    } else {
      setShowScrollDownCta(false);
    }
  }, [messages, isStreaming, userIsNearBottom]);

  return {
    scrollContainerRef,
    userIsNearBottom,
    showScrollDownCta,
    handleScroll,
    forceScrollToBottom,
  };
}
