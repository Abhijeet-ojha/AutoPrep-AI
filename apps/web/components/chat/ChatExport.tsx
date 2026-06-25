import React, { useState, useRef, useEffect } from "react";
import { Download, FileCode, FileType } from "lucide-react";

interface ChatExportProps {
  exportMarkdown: () => void;
  exportPDF: () => void;
  isExporting: boolean;
}

export const ChatExport: React.FC<ChatExportProps> = React.memo(({
  exportMarkdown,
  exportPDF,
  isExporting,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(prev => !prev)}
        disabled={isExporting}
        title="Export options"
        className="p-1.5 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded text-slate-500 dark:text-zinc-400 transition-colors disabled:opacity-50"
      >
        <Download className="h-3.5 w-3.5" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-850 rounded-xl shadow-xl z-30 py-1 animate-slide-up">
          <button
            type="button"
            onClick={() => {
              exportMarkdown();
              setIsOpen(false);
            }}
            className="flex items-center gap-2 px-3 py-2 w-full text-left text-xs text-slate-650 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors"
          >
            <FileCode className="h-3.5 w-3.5 text-blue-500" />
            Export Markdown (.md)
          </button>
          
          <button
            type="button"
            onClick={() => {
              exportPDF();
              setIsOpen(false);
            }}
            className="flex items-center gap-2 px-3 py-2 w-full text-left text-xs text-slate-655 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors"
          >
            <FileType className="h-3.5 w-3.5 text-red-550" />
            Export PDF Report (.pdf)
          </button>
        </div>
      )}
    </div>
  );
});

ChatExport.displayName = "ChatExport";
