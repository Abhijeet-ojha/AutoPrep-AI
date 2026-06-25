import { useState, useEffect, useRef } from "react";
import { TIMINGS } from "../constants";

export function useChatSuggestions(incomingSuggestions: string[]) {
  const [chips, setChips] = useState<string[]>(incomingSuggestions);
  const [visible, setVisible] = useState(true);
  const prevSuggestionsRef = useRef<string[]>(incomingSuggestions);

  useEffect(() => {
    // If suggestions list changed, trigger fade-out, replace list, then fade-in
    const hasChanged = JSON.stringify(prevSuggestionsRef.current) !== JSON.stringify(incomingSuggestions);
    if (hasChanged) {
      prevSuggestionsRef.current = incomingSuggestions;
      setVisible(false);
      
      const timer = setTimeout(() => {
        setChips(incomingSuggestions);
        setVisible(true);
      }, TIMINGS.chipTransitionMs);
      
      return () => clearTimeout(timer);
    }
  }, [incomingSuggestions]);

  return {
    chips,
    visible,
  };
}
