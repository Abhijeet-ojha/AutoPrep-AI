import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { Message } from "../types";

export function useChatSearch(messages: Message[]) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [currentMatchIdx, setCurrentMatchIdx] = useState(0);

  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Computes which message indices contain search matches
  const matchIndices = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const queryLower = searchQuery.toLowerCase();
    return messages
      .map((msg, idx) => (msg.message.toLowerCase().includes(queryLower) ? idx : -1))
      .filter((idx) => idx !== -1);
  }, [messages, searchQuery]);

  // Navigate matching indices
  const nextMatch = useCallback(() => {
    if (matchIndices.length === 0) return;
    setCurrentMatchIdx((prev) => (prev + 1) % matchIndices.length);
  }, [matchIndices]);

  const prevMatch = useCallback(() => {
    if (matchIndices.length === 0) return;
    setCurrentMatchIdx((prev) => (prev - 1 + matchIndices.length) % matchIndices.length);
  }, [matchIndices]);

  const clearSearch = useCallback(() => {
    setSearchQuery("");
    setShowSearch(false);
    setCurrentMatchIdx(0);
  }, []);

  // Listen to keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        setShowSearch(true);
        // Focus inside the search bar on next frame
        setTimeout(() => searchInputRef.current?.focus(), 50);
      } else if (e.key === "Escape" && showSearch) {
        e.preventDefault();
        clearSearch();
      } else if (e.key === "Enter" && showSearch) {
        e.preventDefault();
        if (e.shiftKey) {
          prevMatch();
        } else {
          nextMatch();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showSearch, nextMatch, prevMatch, clearSearch]);

  // Reset match pointer if matching list shrinks
  useEffect(() => {
    if (currentMatchIdx >= matchIndices.length && matchIndices.length > 0) {
      setCurrentMatchIdx(0);
    }
  }, [matchIndices, currentMatchIdx]);

  return {
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
  };
}
