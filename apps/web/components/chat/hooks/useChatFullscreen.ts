import { useState, useEffect, useRef, useCallback } from "react";

export function useChatFullscreen() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [mounted, setMounted] = useState(false);
  const prevActiveElementRef = useRef<HTMLElement | null>(null);
  const modalContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const openFullscreen = useCallback(() => {
    prevActiveElementRef.current = document.activeElement as HTMLElement;
    setIsExpanded(true);
    // Lock scroll
    document.body.style.overflow = "hidden";
  }, []);

  const closeFullscreen = useCallback(() => {
    setIsExpanded(false);
    document.body.style.overflow = "";
    
    // Restore focus
    if (prevActiveElementRef.current) {
      prevActiveElementRef.current.focus();
    }
  }, []);

  // Handle ESC closing and Focus Trapping
  useEffect(() => {
    if (!isExpanded) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeFullscreen();
      } else if (e.key === "Tab" && modalContainerRef.current) {
        // Focus trap
        const focusableElements = modalContainerRef.current.querySelectorAll(
          'a[href], button, textarea, input, select, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusableElements[0] as HTMLElement;
        const last = focusableElements[focusableElements.length - 1] as HTMLElement;

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isExpanded, closeFullscreen]);

  return {
    isExpanded,
    mounted,
    modalContainerRef,
    openFullscreen,
    closeFullscreen,
  };
}
