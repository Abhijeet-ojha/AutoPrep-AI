"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { X } from "lucide-react";

const Plot = dynamic(() => import("react-plotly.js"), { 
  ssr: false, 
  loading: () => (
    <div className="h-full w-full flex flex-col items-center justify-center text-slate-400 dark:text-zinc-500 space-y-2">
      <div className="h-6 w-6 rounded-full border-2 border-slate-300 dark:border-zinc-600 border-t-red-500 animate-spin" />
      <span className="text-xs font-semibold">Loading Chart Modal Spec...</span>
    </div>
  )
}) as any;

type ChartModalProps = {
  isOpen: boolean;
  onClose: () => void;
  chart: {
    title: string;
    data: any[];
    layout: any;
  } | null;
};

export default function ChartModal({ isOpen, onClose, chart }: ChartModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!isOpen || !chart) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-fade-in"
      onClick={onClose}
    >
      <div 
        className="bg-white dark:bg-zinc-900 overflow-hidden flex flex-col shadow-2xl border border-slate-200/50 dark:border-zinc-800 transition-all duration-300 transform scale-100 w-full h-full md:w-[95vw] md:h-[90vh] lg:w-[90vw] lg:h-[90vh] md:rounded-3xl relative p-6 max-sm:p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-[calc(1rem+env(safe-area-inset-top))] px-[calc(1rem+env(safe-area-inset-left))]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex justify-between items-center mb-4 shrink-0">
          <h3 className="title text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-50 uppercase tracking-wide">
            {chart.title}
          </h3>
          <button 
            onClick={onClose}
            className="p-3 rounded-full hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-400 hover:text-slate-650 dark:hover:text-zinc-200 active:scale-95 transition-all min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        {/* Modal Body / Plot Area */}
        <div className="flex-1 w-full min-h-0 relative flex justify-center items-center">
          <Plot
            data={chart.data}
            layout={{
              ...chart.layout,
              autosize: true,
              font: { family: "IBM Plex Sans, sans-serif", size: 11, color: "#9ca3af" },
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              xaxis: { 
                ...chart.layout?.xaxis, 
                gridcolor: "rgba(156,163,175,0.08)", 
                linecolor: "rgba(156,163,175,0.15)", 
                tickcolor: "rgba(156,163,175,0.15)" 
              },
              yaxis: { 
                ...chart.layout?.yaxis, 
                gridcolor: "rgba(156,163,175,0.08)", 
                linecolor: "rgba(156,163,175,0.15)", 
                tickcolor: "rgba(156,163,175,0.15)" 
              }
            }}
            style={{ width: "100%", height: "100%" }}
            config={{ responsive: true, displayModeBar: true }}
          />
        </div>
      </div>
    </div>
  );
}
