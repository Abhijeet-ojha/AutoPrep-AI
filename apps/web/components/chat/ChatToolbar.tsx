import React, { useState } from "react";
import { MoreHorizontal, Copy, Edit, RotateCcw, X, Check } from "lucide-react";

interface ChatToolbarProps {
  role: "user" | "assistant";
  copied: boolean;
  onCopy: () => void;
  onEdit?: () => void;
  onRegenerate?: () => void;
  isLastAssistantMessage?: boolean;
  isGenerating?: boolean;
}

export const ChatToolbar: React.FC<ChatToolbarProps> = ({
  role,
  copied,
  onCopy,
  onEdit,
  onRegenerate,
  isLastAssistantMessage = false,
  isGenerating = false,
}) => {
  const [isOpenMobileMenu, setIsOpenMobileMenu] = useState(false);

  if (isGenerating) return null;

  return (
    <>
      {/* Desktop Toolbar: Hover visible, absolute positioned */}
      <div className="hidden md:flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all duration-200 absolute right-2 top-2 z-10">
        {role === "user" ? (
          onEdit && (
            <button
              type="button"
              onClick={onEdit}
              title="Edit prompt"
              className="p-1 hover:bg-slate-800 dark:hover:bg-zinc-200 rounded text-slate-400 hover:text-slate-200 dark:text-zinc-500 dark:hover:text-zinc-800 transition-colors"
            >
              <Edit className="h-3.5 w-3.5" />
            </button>
          )
        ) : (
          <>
            <button
              type="button"
              onClick={onCopy}
              title="Copy message"
              className="p-1 hover:bg-slate-100 dark:hover:bg-zinc-700/50 rounded text-slate-400 hover:text-slate-650 dark:text-zinc-550 dark:hover:text-zinc-300 transition-colors"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-550" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
            {isLastAssistantMessage && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                title="Regenerate last response"
                className="p-1 hover:bg-slate-100 dark:hover:bg-zinc-700/50 rounded text-slate-400 hover:text-slate-650 dark:text-zinc-550 dark:hover:text-zinc-300 transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            )}
          </>
        )}
      </div>

      {/* Mobile Actions: A more-actions trigger and a bottom sheet menu */}
      <div className="flex md:hidden absolute right-1 top-1 z-10">
        <button
          type="button"
          onClick={() => setIsOpenMobileMenu(true)}
          className="p-1.5 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-full text-slate-400 dark:text-zinc-500 transition-colors"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>

      {/* Mobile Slide-up Bottom Sheet */}
      {isOpenMobileMenu && (
        <div className="fixed inset-0 bg-slate-900/60 dark:bg-black/80 backdrop-blur-sm z-[999] flex items-end justify-center md:hidden animate-fade-in">
          {/* Overlay click to close */}
          <div className="absolute inset-0" onClick={() => setIsOpenMobileMenu(false)} />
          
          {/* Sheet body */}
          <div className="relative w-full bg-white dark:bg-zinc-900 rounded-t-2xl shadow-xl z-10 p-5 max-w-md animate-slide-up border-t border-slate-100 dark:border-zinc-800">
            {/* Grab handle decoration */}
            <div className="mx-auto w-12 h-1 bg-slate-200 dark:bg-zinc-700 rounded-full mb-4" />

            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider">Message Actions</h4>
              <button
                type="button"
                onClick={() => setIsOpenMobileMenu(false)}
                className="p-1 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-full text-slate-400 dark:text-zinc-500"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-2.5">
              {role === "user" ? (
                onEdit && (
                  <button
                    type="button"
                    onClick={() => {
                      onEdit();
                      setIsOpenMobileMenu(false);
                    }}
                    className="flex items-center gap-3 w-full px-4 py-3 text-sm text-left font-medium text-slate-700 dark:text-zinc-350 hover:bg-slate-50 dark:hover:bg-zinc-800/50 rounded-xl transition-all"
                  >
                    <Edit className="h-4 w-4 text-indigo-500" />
                    Edit message prompt
                  </button>
                )
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      onCopy();
                      setIsOpenMobileMenu(false);
                    }}
                    className="flex items-center gap-3 w-full px-4 py-3 text-sm text-left font-medium text-slate-700 dark:text-zinc-350 hover:bg-slate-50 dark:hover:bg-zinc-800/50 rounded-xl transition-all"
                  >
                    {copied ? (
                      <>
                        <Check className="h-4 w-4 text-emerald-550" />
                        Copied to clipboard
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4 text-blue-500" />
                        Copy text content
                      </>
                    )}
                  </button>

                  {isLastAssistantMessage && onRegenerate && (
                    <button
                      type="button"
                      onClick={() => {
                        onRegenerate();
                        setIsOpenMobileMenu(false);
                      }}
                      className="flex items-center gap-3 w-full px-4 py-3 text-sm text-left font-medium text-slate-700 dark:text-zinc-350 hover:bg-slate-50 dark:hover:bg-zinc-800/50 rounded-xl transition-all"
                    >
                      <RotateCcw className="h-4 w-4 text-amber-500 animate-spin-hover" />
                      Regenerate response
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
