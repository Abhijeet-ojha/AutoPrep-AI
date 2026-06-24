"use client";

import { FormEvent, useState, useEffect, useRef } from "react";
import { postJSON } from "@/lib/api";
import { Send, Sparkles, User, Bot, Loader2, AlertCircle } from "lucide-react";

type Message = {
  role: "user" | "assistant";
  message: string;
};

export function ChatPanel({ datasetId, initialHistory = [] }: { datasetId: string, initialHistory?: Message[] }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [userIsNearBottom, setUserIsNearBottom] = useState(true);

  // Initialize messages from history or add a welcoming assistant bubble
  useEffect(() => {
    if (initialHistory && initialHistory.length > 0) {
      setMessages(initialHistory);
    } else {
      setMessages([
        {
          role: "assistant",
          message: "Hello! I am your Dataset Copilot. I've analyzed your data and cleaned duplicate rows, handled missing values, and calculated statistical summaries. Ask me anything about the data or choose from one of the quick start questions below!"
        }
      ]);
    }
  }, [initialHistory]);

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) return;
    // If the user is within 30px of the bottom, they are considered near the bottom
    const isNear = container.scrollHeight - container.scrollTop - container.clientHeight <= 30;
    setUserIsNearBottom(isNear);
  };

  // Scroll to bottom of chat if user is near bottom or the last message is a user message
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const lastMessage = messages[messages.length - 1];
    const isLastUser = lastMessage?.role === "user";

    if (userIsNearBottom || isLastUser) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: "smooth"
      });
    }
  }, [messages, loading]);

  const ask = async (text: string) => {
    if (!text.trim() || loading) return;
    
    setError(null);
    setLoading(true);
    
    // Add user message
    const userMsg: Message = { role: "user", message: text };
    setMessages(prev => [...prev, userMsg]);
    
    try {
      const data = await postJSON(`/datasets/${datasetId}/copilot`, { message: text });
      
      const assistantMsg: Message = { role: "assistant", message: data.response };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to receive a response from Copilot. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    ask(question);
    setQuestion("");
  };

  const starterChips = [
    "Explain dataset quality",
    "Is this dataset ready for machine learning?",
    "What cleaning actions were applied?",
    "What model should I use?",
    "What are the most important features?"
  ];

  return (
    <div className="flex flex-col h-[520px] border border-slate-200 dark:border-zinc-800 rounded-2xl bg-slate-50/50 dark:bg-zinc-900/30 overflow-hidden shadow-inner">
      {/* Header section to the Copilot Card */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-slate-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-sm shrink-0">
        <div className="h-6 w-6 rounded bg-red-100 dark:bg-red-950/40 text-red-600 dark:text-red-400 flex items-center justify-center">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
        <div>
          <h3 className="text-xs font-bold text-slate-800 dark:text-zinc-200 uppercase tracking-wide">AI Copilot</h3>
          <p className="text-[10px] text-slate-400 dark:text-zinc-500 font-medium">Dataset insights & cleaning expert</p>
        </div>
      </div>

      {/* Messages Area */}
      <div 
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-3 max-w-[85%] ${
              msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            }`}
          >
            <div
              className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                msg.role === "user"
                  ? "bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "bg-red-500 text-white"
              }`}
            >
              {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            
            <div
              className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
                msg.role === "user"
                  ? "bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900 rounded-tr-none"
                  : "bg-white text-slate-800 dark:bg-zinc-800 dark:text-zinc-100 border border-slate-100 dark:border-zinc-750 rounded-tl-none"
              }`}
            >
              {msg.message}
            </div>
          </div>
        ))}
        
        {/* Typing / Loading Indicator */}
        {loading && (
          <div className="flex items-start gap-3 mr-auto max-w-[85%]">
            <div className="h-8 w-8 rounded-lg bg-red-500 text-white flex items-center justify-center shrink-0">
              <Bot className="h-4 w-4 animate-pulse" />
            </div>
            <div className="rounded-2xl rounded-tl-none bg-white border border-slate-100 dark:bg-zinc-800 dark:border-zinc-750 px-4 py-3 flex items-center space-x-2 shadow-sm animate-pulse">
              <span className="text-xs text-slate-400 dark:text-zinc-500 font-semibold uppercase">Copilot is processing</span>
              <Loader2 className="h-4 w-4 text-red-500 animate-spin" />
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-3 mx-auto max-w-[90%] bg-red-50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/30 p-3.5 rounded-xl text-red-600 dark:text-red-400 text-xs font-semibold">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p>Copilot Request Failed</p>
              <p className="text-[10px] text-slate-400 dark:text-zinc-500 font-medium mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Starter Chips Panel */}
      <div className="px-4 py-2 border-t border-slate-200/60 dark:border-zinc-800/60 bg-white/40 dark:bg-zinc-900/40 shrink-0">
        <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
          <Sparkles className="h-3 w-3 text-amber-500" /> Suggested Queries
        </p>
        <div className="flex flex-wrap gap-1.5 max-h-[85px] overflow-y-auto py-0.5 pr-2">
          {starterChips.map((chip, idx) => (
            <button
              key={idx}
              disabled={loading}
              onClick={() => ask(chip)}
              className="text-xs text-slate-600 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700/80 px-2.5 py-1 rounded-lg border border-slate-200/40 dark:border-zinc-750/30 transition-all font-medium disabled:opacity-50 text-left"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Input box form */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex gap-2 items-center shrink-0">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask Copilot about your dataset quality, outliers, or modeling ideas..."
          disabled={loading}
          className="flex-1 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-950 px-4 py-3 text-sm text-slate-800 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-slate-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="h-11 w-11 rounded-xl bg-slate-900 hover:bg-slate-850 dark:bg-zinc-50 dark:hover:bg-zinc-200 text-white dark:text-zinc-950 flex items-center justify-center shrink-0 shadow-md transition-all disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
