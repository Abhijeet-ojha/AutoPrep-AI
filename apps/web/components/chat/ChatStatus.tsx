import React from "react";
import { StreamStatus } from "./types";

interface ChatStatusProps {
  status: StreamStatus;
}

export const ChatStatus: React.FC<ChatStatusProps> = React.memo(({ status }) => {
  if (!status) return null;

  return (
    <div className="flex items-center gap-2.5 px-4 py-2 bg-slate-50/80 dark:bg-zinc-850/30 border border-slate-100 dark:border-zinc-800/40 rounded-xl max-w-max mx-auto shadow-sm animate-fade-in my-2 select-none">
      {/* Premium custom rotating gradient spinner */}
      <div className="relative h-4 w-4 shrink-0">
        <div className="absolute inset-0 rounded-full border-2 border-slate-200 dark:border-zinc-800" />
        <div className="absolute inset-0 rounded-full border-2 border-t-red-500 border-r-transparent border-b-transparent border-l-transparent animate-spin" />
      </div>
      
      <span className="text-xs font-semibold text-slate-650 dark:text-zinc-400 animate-pulse tracking-wide">
        {status}...
      </span>
    </div>
  );
});

ChatStatus.displayName = "ChatStatus";
