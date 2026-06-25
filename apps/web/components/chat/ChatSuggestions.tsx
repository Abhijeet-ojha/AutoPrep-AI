import React from "react";
import { Sparkles } from "lucide-react";

interface ChatSuggestionsProps {
  suggestions: string[];
  visible: boolean;
  onSuggestionClick: (suggestion: string) => void;
  disabled: boolean;
}

export const ChatSuggestions: React.FC<ChatSuggestionsProps> = React.memo(({
  suggestions,
  visible,
  onSuggestionClick,
  disabled,
}) => {
  if (suggestions.length === 0) return null;

  return (
    <div className="px-4 py-2 border-t border-slate-200/60 dark:border-zinc-800/60 bg-white/40 dark:bg-zinc-900/40 shrink-0 select-none">
      <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
        <Sparkles className="h-3 w-3 text-amber-500" /> Suggested Queries
      </p>
      
      <div 
        className={`flex flex-wrap gap-1.5 max-h-[85px] overflow-y-auto py-0.5 pr-2 transition-all duration-300 transform ease-in-out ${
          visible 
            ? "opacity-100 translate-y-0" 
            : "opacity-0 translate-y-1"
        }`}
      >
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            disabled={disabled}
            type="button"
            onClick={() => onSuggestionClick(suggestion)}
            className="text-xs text-slate-650 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700/80 px-2.5 py-1 rounded-lg border border-slate-200/40 dark:border-zinc-750/30 transition-all font-medium disabled:opacity-50 text-left active:scale-[0.98] focus:outline-none focus:ring-1 focus:ring-slate-400"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
});

ChatSuggestions.displayName = "ChatSuggestions";
