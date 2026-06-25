import React from "react";
import { Sparkles, Maximize2, Minimize2, Search, X, ChevronUp, ChevronDown } from "lucide-react";
import { ChatExport } from "./ChatExport";

interface ChatHeaderProps {
  isExpanded: boolean;
  showSearch: boolean;
  setShowSearch: (show: boolean) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  matchIndices: number[];
  currentMatchIdx: number;
  nextMatch: () => void;
  prevMatch: () => void;
  clearSearch: () => void;
  openFullscreen: () => void;
  closeFullscreen: () => void;
  exportMarkdown: (msgOnly?: any) => void;
  exportPDF: (msgOnly?: any) => void;
  isExporting: boolean;
  searchInputRef: React.RefObject<HTMLInputElement>;
}

export const ChatHeader: React.FC<ChatHeaderProps> = React.memo((props) => {
  const {
    isExpanded,
    showSearch,
    setShowSearch,
    searchQuery,
    setSearchQuery,
    matchIndices,
    currentMatchIdx,
    nextMatch,
    prevMatch,
    clearSearch,
    openFullscreen,
    closeFullscreen,
    exportMarkdown,
    exportPDF,
    isExporting,
    searchInputRef,
  } = props;

  return (
    <div className="flex flex-col border-b border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-sm shrink-0 z-10 transition-all duration-300">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="h-6 w-6 rounded bg-red-100 dark:bg-red-950/40 text-red-600 dark:text-red-400 flex items-center justify-center">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-800 dark:text-zinc-200 uppercase tracking-wide">AI Copilot</h3>
            <p className="text-[10px] text-slate-400 dark:text-zinc-500 font-medium">Dataset insights & cleaning expert</p>
          </div>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-1.5 relative">
          <button
            type="button"
            onClick={() => setShowSearch(!showSearch)}
            title="Search conversation (Ctrl + F)"
            className={`p-1.5 rounded transition-all ${
              showSearch 
                ? "bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200" 
                : "hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 dark:text-zinc-400"
            }`}
          >
            <Search className="h-3.5 w-3.5" />
          </button>

          {/* Export Dropdown Component */}
          <ChatExport
            exportMarkdown={exportMarkdown}
            exportPDF={exportPDF}
            isExporting={isExporting}
          />

          <button
            type="button"
            onClick={isExpanded ? closeFullscreen : openFullscreen}
            title={isExpanded ? "Collapse Chat" : "Expand Chat"}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded text-slate-500 dark:text-zinc-400 transition-colors"
          >
            {isExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Inline Search Bar */}
      {showSearch && (
        <div className="flex items-center gap-2 px-4 py-2 border-t border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-950/20 animate-slide-up">
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search messages..."
            className="flex-1 text-xs bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
          {searchQuery && (
            <div className="flex items-center gap-1.5 shrink-0 text-[10px] text-slate-400 dark:text-zinc-500 font-semibold select-none">
              <span>
                {matchIndices.length > 0 ? `${currentMatchIdx + 1} of ${matchIndices.length}` : "No matches"}
              </span>
              {matchIndices.length > 0 && (
                <div className="flex items-center border border-slate-200 dark:border-zinc-800 rounded-md overflow-hidden bg-white dark:bg-zinc-950">
                  <button
                    type="button"
                    onClick={prevMatch}
                    className="p-1 hover:bg-slate-50 dark:hover:bg-zinc-800 border-r border-slate-200 dark:border-zinc-800"
                  >
                    <ChevronUp className="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    onClick={nextMatch}
                    className="p-1 hover:bg-slate-50 dark:hover:bg-zinc-800"
                  >
                    <ChevronDown className="h-3 w-3" />
                  </button>
                </div>
              )}
            </div>
          )}
          <button
            type="button"
            onClick={clearSearch}
            className="p-1 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded text-slate-400 dark:text-zinc-500"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
});

ChatHeader.displayName = "ChatHeader";
