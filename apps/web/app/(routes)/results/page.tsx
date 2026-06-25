"use client";

import React, { useEffect, useState, useMemo, Suspense } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { downloadCleanedCSV, downloadReport, downloadCleaningLog } from "@/lib/api";
import { 
  Database, 
  LayoutGrid, 
  AlertTriangle, 
  Copy, 
  Binary, 
  Tag, 
  CheckCircle2, 
  ArrowLeft, 
  Download, 
  FileText, 
  HelpCircle, 
  Sparkles, 
  Flame, 
  ShieldAlert, 
  AlertCircle,
  Maximize2,
  X
} from "lucide-react";

const Plot = dynamic(() => import("react-plotly.js"), { 
  ssr: false, 
  loading: () => <SkeletonChart />
}) as any;

const ChatPanel = dynamic(() => import("@/components/ChatPanel").then(mod => mod.ChatPanel), {
  ssr: false,
  loading: () => (
    <div className="h-[520px] w-full rounded-2xl bg-slate-100 dark:bg-zinc-800 animate-pulse flex flex-col items-center justify-center text-slate-400 dark:text-zinc-500 space-y-2">
      <div className="h-6 w-6 rounded-full border-2 border-slate-300 dark:border-zinc-600 border-t-red-500 animate-spin" />
      <span className="text-xs font-semibold">Loading Copilot...</span>
    </div>
  )
});

const ChartModal = dynamic(() => import("@/components/ChartModal"), {
  ssr: false
});

const ChartCard = React.memo(({ chart, index, onExpand }: { chart: any, index: number, onExpand: (idx: number) => void }) => {
  return (
    <div className="card p-4 flex flex-col justify-between hover:shadow-md transition-all duration-300 relative group overflow-hidden">
      <div className="flex justify-between items-center mb-3">
        <h4 className="title text-xs font-extrabold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">
          {chart.title}
        </h4>
        <button 
          onClick={() => onExpand(index)}
          className="p-3 rounded-xl border border-slate-200 dark:border-zinc-800 text-slate-500 dark:text-zinc-400 bg-slate-50/50 dark:bg-zinc-900 hover:text-slate-650 dark:hover:text-zinc-300 md:hidden active:scale-95 transition-transform flex items-center justify-center shrink-0 min-h-[48px] min-w-[48px]"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>
      <div className="w-full flex justify-center relative">
        <Plot
          data={chart.data}
          layout={{
            ...chart.layout,
            autosize: true,
            font: { family: "IBM Plex Sans, sans-serif", size: 10, color: "#9ca3af" },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            height: 240,
            margin: { l: 45, r: 15, b: 45, t: 15 },
            xaxis: { ...chart.layout?.xaxis, gridcolor: "rgba(156,163,175,0.08)", linecolor: "rgba(156,163,175,0.15)", tickcolor: "rgba(156,163,175,0.15)" },
            yaxis: { ...chart.layout?.yaxis, gridcolor: "rgba(156,163,175,0.08)", linecolor: "rgba(156,163,175,0.15)", tickcolor: "rgba(156,163,175,0.15)" }
          }}
          style={{ width: "100%", height: 240 }}
          config={{ responsive: true, displayModeBar: false }}
        />
        
        {/* Hover Overlay */}
        <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-all duration-300 flex items-center justify-center rounded-2xl z-10 hidden md:flex">
          <button
            onClick={() => onExpand(index)}
            className="bg-white dark:bg-zinc-900 text-slate-800 dark:text-zinc-200 px-5 py-3 rounded-xl text-sm font-bold shadow-lg transform scale-90 group-hover:scale-100 transition-all duration-300 flex items-center gap-2 active:scale-95"
          >
            <span>🔍</span> View Full Screen
          </button>
        </div>
      </div>
    </div>
  );
});
ChartCard.displayName = "ChartCard";

type ResultsData = {
  session_token: string;
  dataset_summary: {
    dataset_id: string;
    filename: string;
    file_size_bytes: number;
    rows: number;
    columns: number;
  };
  profile: any;
  quality: any;
  health: any;
  health_score: number;
  health_explanation: string;
  readiness: any;
  visual_insights: any[];
  cleaning_logs: any[];
  cleaning_impact?: {
    rows_before: number;
    rows_after: number;
    missing_values_fixed: number;
    duplicates_removed: number;
    outliers_treated: number;
    columns_modified: number;
    cells_modified: number;
    original_missing_count?: number;
    original_duplicate_count?: number;
    original_outlier_count?: number;
  };
  column_semantics?: Record<string, {
    type: string;
    confidence: number;
    strategy: string;
    reason: string;
  }>;
  column_impacts?: Array<{
    column: string;
    missing_before: number;
    missing_after: number;
    outliers_before: number;
    outliers_after: number;
  }>;
  issues: Array<{
    column: string;
    issue: string;
    severity: string;
    metric_value: string;
    affected_rows: number;
    recommendation: string;
  }>;
  insights: any[];
  chat_history?: any[];
};

function SkeletonChart() {
  return (
    <div className="h-[260px] w-full rounded-2xl bg-slate-100 dark:bg-zinc-800 animate-pulse flex flex-col items-center justify-center text-slate-400 dark:text-zinc-500 space-y-2">
      <div className="h-6 w-6 rounded-full border-2 border-slate-300 dark:border-zinc-600 border-t-red-500 animate-spin" />
      <span className="text-xs font-semibold">Generating Chart Spec...</span>
    </div>
  );
}

function ResultsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");

  const [data, setData] = useState<ResultsData | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [downloadingLog, setDownloadingLog] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [activeTab, setActiveTab] = useState<"findings" | "impact">("findings");
  const [error, setError] = useState<string | null>(null);
  const [activeChartModal, setActiveChartModal] = useState<number | null>(null);

  // Keypress listeners are handled internally by dynamic modal components

  useEffect(() => {
    // Load dataset metadata strictly from sessionStorage
    try {
      const cached = sessionStorage.getItem("autoprep_results");
      if (cached) {
        const parsed = JSON.parse(cached) as ResultsData;
        if (!sessionId || parsed.dataset_summary?.dataset_id === sessionId) {
          setData(parsed);
          return;
        }
      }
      // If missing or mismatched, flag session as expired
      setSessionExpired(true);
    } catch (e) {
      console.error("Failed to read sessionStorage results", e);
      setSessionExpired(true);
    }
  }, [sessionId]);

  const totalMissing = useMemo(() => {
    if (!data || !data.quality?.missing?.by_column) return 0;
    return Object.values(data.quality.missing.by_column).reduce((a: any, b: any) => Number(a) + Number(b), 0) as number;
  }, [data]);

  const totalOutliers = useMemo(() => {
    if (!data || !data.quality?.outliers?.iqr) return 0;
    return Object.values(data.quality.outliers.iqr).reduce((a: any, b: any) => Number(a) + Number(b), 0) as number;
  }, [data]);

  // Parse health score explanation lines into clean lists
  const parsedHealth = useMemo(() => {
    if (!data || !data.health_explanation) return { issues: [], effort: "Low" };
    const lines = data.health_explanation.split("\n");
    const issues: string[] = [];
    let effort = "Low";
    let inIssues = false;
    let inEffort = false;

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("Primary Issues:")) {
        inIssues = true;
        inEffort = false;
        continue;
      }
      if (trimmed.startsWith("Estimated Cleaning Effort:")) {
        inIssues = false;
        inEffort = true;
        continue;
      }
      if (inIssues && trimmed.startsWith("-")) {
        issues.push(trimmed.replace("-", "").trim());
      }
      if (inEffort && trimmed) {
        effort = trimmed.replace("-", "").trim();
      }
    }
    return { issues, effort };
  }, [data]);

  const handleDownload = async () => {
    if (!data) return;
    setError(null);
    setDownloading(true);
    try {
      await downloadCleanedCSV(data.dataset_summary.dataset_id, data.dataset_summary.filename);
      // Evict credentials from sessionStorage immediately upon download completion for privacy-first
      sessionStorage.removeItem("autoprep_session_id");
      sessionStorage.removeItem("autoprep_session_token");
      sessionStorage.removeItem("autoprep_results");
      
      // Delay briefly then push back to landing or show expired
      setTimeout(() => {
        router.push("/");
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed. The session may have expired.");
      setDownloading(false);
    }
  };

  const handleReport = async () => {
    if (!data) return;
    setError(null);
    setReporting(true);
    try {
      await downloadReport(data.dataset_summary.dataset_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to retrieve PDF report.");
    } finally {
      setReporting(false);
    }
  };

  const handleDownloadLog = async () => {
    if (!data) return;
    setError(null);
    setDownloadingLog(true);
    try {
      await downloadCleaningLog(data.dataset_summary.dataset_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to retrieve JSON log.");
    } finally {
      setDownloadingLog(false);
    }
  };

  // UI state: Session Expired Screen
  if (sessionExpired) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 min-h-[85vh] flex flex-col justify-between">
        <header className="flex justify-between items-center py-4 border-b border-slate-200/60 dark:border-zinc-800/60">
          <span className="title font-bold text-lg text-slate-900 dark:text-zinc-50">AutoPrep AI</span>
        </header>
        <main className="flex flex-col items-center justify-center flex-1 max-w-md mx-auto text-center space-y-6 px-4">
          <div className="h-16 w-16 rounded-2xl bg-amber-50 dark:bg-amber-950/20 text-amber-500 flex items-center justify-center border border-amber-200/40 shadow-sm animate-pulse">
            <ShieldAlert className="h-8 w-8" />
          </div>
          <div className="space-y-2">
            <h2 className="title text-3xl font-extrabold text-slate-900 dark:text-zinc-50 tracking-tight">🔒 Privacy Protected</h2>
            <p className="text-sm text-slate-500 dark:text-zinc-400 font-medium leading-relaxed whitespace-pre-line">
              For privacy reasons your dataset and generated files
              have been permanently removed from our servers.
            </p>
          </div>
          <Link 
            href="/"
            className="w-full rounded-xl bg-slate-900 dark:bg-zinc-50 text-white dark:text-zinc-950 text-center py-3.5 text-sm font-extrabold shadow-lg hover:bg-slate-800 dark:hover:bg-zinc-200 transition-all"
          >
            Upload New Dataset
          </Link>
        </main>
        <footer className="py-8 text-center text-xs text-slate-400 dark:text-zinc-500 border-t border-slate-200/60 dark:border-zinc-800/60">
          AutoPrep AI © 2026. Zero persistence session expiration.
        </footer>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center space-y-4 dark:bg-zinc-950">
        <div className="h-10 w-10 border-4 border-slate-200 dark:border-zinc-800 border-t-red-500 animate-spin rounded-full" />
        <span className="text-xs text-slate-500 font-bold uppercase tracking-wider animate-pulse">Loading dashboard...</span>
      </div>
    );
  }

  // Circular progress calculations for the Health score gauge
  const healthScore = data.health_score;
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (healthScore / 100) * circumference;

  // Determine health color badge
  const healthColor = healthScore >= 90 
    ? "text-emerald-500 stroke-emerald-500" 
    : healthScore >= 70 
    ? "text-amber-500 stroke-amber-500" 
    : "text-red-500 stroke-red-500";

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 space-y-8 pb-16">
      {/* Top Navigation */}
      <header className="flex justify-between items-center w-full py-4 border-b border-slate-200/60 dark:border-zinc-800/60">
        <div className="flex items-center gap-4">
          <Link 
            href="/" 
            className="h-12 w-12 rounded-xl border border-slate-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 hover:bg-slate-50 dark:hover:bg-zinc-800 shadow-sm text-slate-600 dark:text-zinc-400 active:scale-[0.98] transition-transform flex items-center justify-center shrink-0"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <span className="title font-extrabold text-xl text-slate-900 dark:text-zinc-50 block leading-tight">
              Analysis Studio
            </span>
            <span className="text-xs text-slate-400 dark:text-zinc-500 font-semibold tracking-tight">
              File: {data.dataset_summary.filename}
            </span>
          </div>
        </div>
      </header>

      {/* Main grid containing sections */}
      <div className="grid grid-cols-1 lg:grid-cols-10 gap-8">
        
        {/* SECTION 1: Dataset Summary */}
        <section className="col-span-1 lg:col-span-10 order-1 space-y-4">
          <h2 className="title text-lg font-bold text-slate-800 dark:text-zinc-100 flex items-center gap-2">
            <Database className="h-4 w-4 text-red-500" /> Dataset Summary
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div className="card flex flex-col justify-between p-4 hover:-translate-y-0.5 transition-all duration-300">
              <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Rows</span>
              <span className="text-2xl font-black text-slate-900 dark:text-zinc-100 mt-1">{data.dataset_summary.rows.toLocaleString()}</span>
            </div>
            <div className="card flex flex-col justify-between p-4 hover:-translate-y-0.5 transition-all duration-300">
              <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Columns</span>
              <span className="text-2xl font-black text-slate-900 dark:text-zinc-100 mt-1">{data.dataset_summary.columns}</span>
            </div>
            <div className="card flex flex-col justify-between p-4 hover:-translate-y-0.5 transition-all duration-300">
              <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Missing Cells</span>
              <span className={`text-2xl font-black mt-1 ${totalMissing > 0 ? "text-amber-500" : "text-emerald-500"}`}>
                {totalMissing.toLocaleString()}
              </span>
            </div>
            <div className="card flex flex-col justify-between p-4 hover:-translate-y-0.5 transition-all duration-300">
              <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Duplicate Rows</span>
              <span className={`text-2xl font-black mt-1 ${data.quality.duplicates.duplicate_rows > 0 ? "text-amber-500" : "text-emerald-500"}`}>
                {data.quality.duplicates.duplicate_rows}
              </span>
            </div>
            <div className="card flex flex-col justify-between p-4 hover:-translate-y-0.5 transition-all duration-300">
              <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Numeric Columns</span>
              <span className="text-2xl font-black text-slate-900 dark:text-zinc-100 mt-1">{data.profile.roles.numerical?.length || 0}</span>
            </div>
            <div className="card flex flex-col justify-between p-4 hover:-translate-y-0.5 transition-all duration-300">
              <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Categorical Columns</span>
              <span className="text-2xl font-black text-slate-900 dark:text-zinc-100 mt-1">{data.profile.roles.categorical?.length || 0}</span>
            </div>
          </div>
        </section>

        {/* SECTION 2: Health Score */}
        <section className="col-span-1 lg:col-span-10 order-2 space-y-4">
          <h2 className="title text-lg font-bold text-slate-800 dark:text-zinc-100 flex items-center gap-2">
            <Flame className="h-4 w-4 text-red-500" /> Health & Audit findings
          </h2>
          <div className="card grid grid-cols-1 md:grid-cols-3 gap-6 p-6">
            {/* Circular Gauge */}
            <div className="flex flex-col items-center justify-center text-center py-2 border-b md:border-b-0 md:border-r border-slate-100 dark:border-zinc-800 md:pr-6">
              <div className="relative h-28 w-28 flex items-center justify-center">
                <svg className="h-full w-full rotate-[-90deg]">
                  <circle cx="56" cy="56" r={radius} strokeWidth="8" className="stroke-slate-100 dark:stroke-zinc-800" fill="transparent" />
                  <circle 
                    cx="56" 
                    cy="56" 
                    r={radius} 
                    strokeWidth="8" 
                    className={`transition-all duration-500 ${healthColor}`}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    fill="transparent" 
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-2xl font-black text-slate-900 dark:text-zinc-100 leading-none">{healthScore}</span>
                  <span className="text-[10px] text-slate-400 font-bold uppercase mt-1">Health</span>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <span className="text-xs font-bold text-slate-400 dark:text-zinc-500 uppercase">Effort Needed:</span>
                <span className={`text-xs font-extrabold px-2 py-0.5 rounded-full border ${
                  parsedHealth.effort.toLowerCase() === "low" 
                    ? "bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-950/20 dark:text-emerald-400 dark:border-emerald-900/30"
                    : parsedHealth.effort.toLowerCase() === "medium"
                    ? "bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-950/20 dark:text-amber-400 dark:border-amber-900/30"
                    : "bg-red-50 text-red-600 border-red-200 dark:bg-red-950/20 dark:text-red-400 dark:border-red-900/30"
                }`}>
                  {parsedHealth.effort}
                </span>
              </div>
            </div>

            {/* parsed explanation list */}
            <div className="md:col-span-2 flex flex-col justify-center space-y-4">
              <h3 className="title text-sm font-bold text-slate-800 dark:text-zinc-200 uppercase tracking-wide">
                Audit Summary Reasons
              </h3>
              {parsedHealth.issues.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-zinc-400">
                  Perfect dataset profile state. No flags or warnings generated.
                </p>
              ) : (
                <ul className="space-y-2">
                  {parsedHealth.issues.map((issue, idx) => (
                    <li key={idx} className="flex items-start gap-2.5 text-sm text-slate-600 dark:text-zinc-400 animate-fade-in">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0 mt-2" />
                      <span>{issue}</span>
                    </li>
                  ))}
                </ul>
              )}
              
              {data.issues?.length > 0 && (
                <button 
                  onClick={() => setShowAuditModal(true)}
                  className="mt-4 text-xs font-bold text-red-500 hover:text-red-650 uppercase tracking-wider transition-all active:scale-[0.98] h-12 w-full md:w-auto flex items-center justify-center md:justify-start px-4 md:px-0 border border-red-500/20 md:border-transparent rounded-xl md:rounded-none bg-red-50/10 md:bg-transparent shrink-0"
                >
                  View Full Audit Details →
                </button>
              )}
            </div>
          </div>
        </section>

        {/* SECTION 3: Cleaning Actions */}
        <section className="col-span-1 lg:col-span-10 order-3 space-y-4">
          <h2 className="title text-lg font-bold text-slate-800 dark:text-zinc-100 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Applied Cleaning Actions
          </h2>
          <div className="card p-6 space-y-6">
            {data.cleaning_impact && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 dark:bg-zinc-800/40 rounded-xl border border-slate-200/35 dark:border-zinc-700/30 mb-6">
                <div className="flex flex-col">
                  <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Cells Modified</span>
                  <span className="text-lg font-black text-slate-900 dark:text-zinc-100 mt-1">{data.cleaning_impact.cells_modified}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Missing Fixed</span>
                  <span className="text-lg font-black text-slate-900 dark:text-zinc-100 mt-1">
                    {data.cleaning_impact.missing_values_fixed} <span className="text-xs font-semibold text-slate-400">/ {data.cleaning_impact.original_missing_count ?? totalMissing}</span>
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Outliers Treated</span>
                  <span className="text-lg font-black text-slate-900 dark:text-zinc-100 mt-1">
                    {data.cleaning_impact.outliers_treated} <span className="text-xs font-semibold text-slate-400">/ {data.cleaning_impact.original_outlier_count ?? totalOutliers}</span>
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase">Rows Retained</span>
                  <span className="text-lg font-black text-slate-900 dark:text-zinc-100 mt-1">
                    {data.cleaning_impact.rows_after} <span className="text-xs font-semibold text-slate-400">/ {data.cleaning_impact.rows_before}</span>
                  </span>
                </div>
              </div>
            )}
            {data.cleaning_logs.length === 0 ? (
              <div className="text-center py-6 text-slate-500 dark:text-zinc-400 text-sm font-medium">
                The uploaded dataset was fully clean. No imputations or outlier adjustments were needed.
              </div>
            ) : (
              <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-3 space-y-6">
                {data.cleaning_logs.map((log: any, idx: number) => (
                  <div key={idx} className="relative pl-6">
                    <div className="absolute -left-[9px] top-1 h-4.5 w-4.5 rounded-full border-4 border-white dark:border-zinc-900 bg-emerald-500 shadow-sm flex items-center justify-center" />
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
                      <span className="font-bold text-slate-900 dark:text-zinc-100 text-sm sm:text-base capitalize">
                        {log.action?.replace(/_/g, " ")} {log.column ? `on '${log.column}'` : ""}
                      </span>
                      <div className="flex gap-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400 font-mono border border-slate-200/35 dark:border-zinc-700/30 uppercase">
                          Method: {log.method}
                        </span>
                      </div>
                    </div>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1.5 leading-relaxed">
                      Reason: {log.reason}
                    </p>
                    <div className="flex items-center gap-4 mt-2.5 text-[11px] text-slate-400 dark:text-zinc-500 font-bold">
                      <span>Confidence Score: <span className="text-emerald-500">{Math.round(log.confidence * 100)}%</span></span>
                      {log.affected_rows !== undefined && <span>Modified Cells: {log.affected_rows}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* SECTION 4: Visual Insights */}
        <section className="col-span-1 lg:col-span-7 order-4 space-y-4">
          <h2 className="title text-lg font-bold text-slate-800 dark:text-zinc-100 flex items-center gap-2">
            <LayoutGrid className="h-4 w-4 text-cyan-500" /> Visual Exploratory Insights
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {data.visual_insights.length === 0 ? (
              <div className="col-span-full card text-center py-10 text-slate-500 dark:text-zinc-400 text-sm">
                No visual payload config generated for this dataset profile.
              </div>
            ) : (
              data.visual_insights.map((chart: any, index: number) => (
                <ChartCard 
                  key={index} 
                  chart={chart} 
                  index={index} 
                  onExpand={setActiveChartModal} 
                />
              ))
            )}
          </div>
        </section>

        {/* SECTION 5: AI Dataset Copilot */}
        <section className="col-span-1 lg:col-span-3 order-6 md:order-5 lg:order-5 space-y-4">
          <h2 className="title text-lg font-bold text-slate-800 dark:text-zinc-100 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-amber-500" /> AI Dataset Copilot
          </h2>
          <ChatPanel datasetId={data.dataset_summary.dataset_id} initialHistory={data.chat_history} />
        </section>

        {/* SECTION 6: Download Center */}
        <section className="col-span-1 lg:col-span-10 order-5 md:order-6 lg:order-6 space-y-4">
          <h2 className="title text-lg font-bold text-slate-800 dark:text-zinc-100 flex items-center gap-2">
            <Download className="h-4 w-4 text-slate-700 dark:text-zinc-300" /> Download Center
          </h2>
          <div className="card p-6 space-y-6">
            
            {/* Warning banner */}
            <div className="flex items-start gap-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/30 p-4 rounded-xl text-amber-600 dark:text-amber-400 text-xs font-semibold leading-relaxed">
              <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold uppercase tracking-wider mb-0.5">Privacy Action Reminder</p>
                <p className="text-slate-500 dark:text-zinc-400 font-medium">
                  Files are automatically deleted after download or session expiration. Once you click download, all cached files and session state are immediately wiped from our servers.
                </p>
              </div>
            </div>

            {/* Error log if download crashes */}
            {error && (
              <div className="flex items-start gap-3 bg-red-50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/30 p-4 rounded-xl text-red-600 dark:text-red-400 text-xs font-semibold leading-normal animate-fade-in">
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Execution Failure</p>
                  <p className="text-[10px] text-slate-500 dark:text-zinc-400 mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex flex-col md:flex-row gap-4">
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-slate-900 dark:bg-zinc-50 hover:bg-slate-800 dark:hover:bg-zinc-200 text-white dark:text-zinc-950 h-12 text-sm font-extrabold shadow-md transition-all disabled:opacity-50 active:scale-[0.98]"
              >
                {downloading ? (
                  <>
                    <div className="h-4 w-4 border-2 border-white dark:border-zinc-950 border-t-transparent animate-spin rounded-full" />
                    Downloading...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    Download Cleaned CSV
                  </>
                )}
              </button>
              
              <button
                onClick={handleReport}
                disabled={reporting}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 h-12 text-sm font-extrabold shadow-sm transition-all disabled:opacity-50 active:scale-[0.98]"
              >
                {reporting ? (
                  <>
                    <div className="h-4 w-4 border-2 border-slate-700 dark:border-zinc-300 border-t-transparent animate-spin rounded-full" />
                    Preparing Report...
                  </>
                ) : (
                  <>
                    <FileText className="h-4 w-4" />
                    Download Report
                  </>
                )}
              </button>
              
              <button
                onClick={handleDownloadLog}
                disabled={downloadingLog}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 h-12 text-sm font-extrabold shadow-sm transition-all disabled:opacity-50 active:scale-[0.98]"
              >
                {downloadingLog ? (
                  <>
                    <div className="h-4 w-4 border-2 border-slate-700 dark:border-zinc-300 border-t-transparent animate-spin rounded-full" />
                    Preparing Log...
                  </>
                ) : (
                  <>
                    <FileText className="h-4 w-4" />
                    Download Cleaning Log (JSON)
                  </>
                )}
              </button>
            </div>

          </div>
        </section>

      </div>
       {/* Fullscreen Chart Modal */}
      <ChartModal 
        isOpen={activeChartModal !== null} 
        onClose={() => setActiveChartModal(null)} 
        chart={activeChartModal !== null ? data.visual_insights[activeChartModal] : null} 
      />

      {/* Audit Modal */}
      {showAuditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in" onClick={() => setShowAuditModal(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 dark:border-zinc-800" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center shrink-0">
              <h2 className="title text-xl font-bold text-slate-900 dark:text-zinc-50">Detailed Quality Audit</h2>
              <button 
                onClick={() => setShowAuditModal(false)} 
                className="text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 active:scale-95 transition-all h-12 w-12 rounded-full flex items-center justify-center shrink-0"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            
            {/* Tabs header */}
            <div className="px-6 bg-slate-50 dark:bg-zinc-900 border-b border-slate-100 dark:border-zinc-800 flex gap-4 shrink-0">
              <button 
                onClick={() => setActiveTab("findings")}
                className={`py-3 px-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all min-h-[48px] flex items-center ${
                  activeTab === "findings" 
                    ? "border-red-500 text-slate-900 dark:text-zinc-100" 
                    : "border-transparent text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300"
                }`}
              >
                Quality Issues
              </button>
              <button 
                onClick={() => setActiveTab("impact")}
                className={`py-3 px-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all min-h-[48px] flex items-center ${
                  activeTab === "impact" 
                    ? "border-red-500 text-slate-900 dark:text-zinc-100" 
                    : "border-transparent text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300"
                }`}
              >
                Cleaning Impact (Before/After)
              </button>
            </div>
            
            <div className="p-6 overflow-auto">
              {activeTab === "findings" ? (
                <>
                  {/* Desktop Table View */}
                  <table className="hidden md:table w-full text-left text-sm text-slate-600 dark:text-zinc-400">
                    <thead className="text-xs uppercase bg-slate-50 dark:bg-zinc-800 text-slate-500 dark:text-zinc-300">
                      <tr>
                        <th className="px-4 py-3">Column</th>
                        <th className="px-4 py-3">Issue</th>
                        <th className="px-4 py-3">Severity</th>
                        <th className="px-4 py-3">Metric</th>
                        <th className="px-4 py-3">Affected Rows</th>
                        <th className="px-4 py-3">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.issues.map((issue, idx) => (
                        <tr key={idx} className="border-b border-slate-100 dark:border-zinc-800">
                          <td className="px-4 py-3 font-semibold text-slate-900 dark:text-zinc-200">{issue.column}</td>
                          <td className="px-4 py-3">{issue.issue}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              issue.severity === 'High' ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
                              issue.severity === 'Medium' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400' :
                              'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400'
                            }`}>
                              {issue.severity}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">{issue.metric_value}</td>
                          <td className="px-4 py-3">{issue.affected_rows}</td>
                          <td className="px-4 py-3">{issue.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Mobile Stacked Card View */}
                  <div className="block md:hidden space-y-4">
                    {data.issues.map((issue, idx) => (
                      <div key={idx} className="p-4 bg-slate-50 dark:bg-zinc-800 rounded-2xl border border-slate-200/50 dark:border-zinc-800 space-y-2">
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase block">Column</span>
                          <span className="text-sm font-bold text-slate-900 dark:text-zinc-100">{issue.column}</span>
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase block">Issue</span>
                          <span className="text-sm text-slate-700 dark:text-zinc-350">{issue.issue}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase block mb-1">Severity</span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              issue.severity === 'High' ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
                              issue.severity === 'Medium' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400' :
                              'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400'
                            }`}>
                              {issue.severity}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] font-bold text-slate-400 uppercase block">Affected Rows</span>
                            <span className="text-sm font-mono text-slate-700 dark:text-zinc-355">{issue.affected_rows}</span>
                          </div>
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase block">Recommendation</span>
                          <p className="text-xs text-slate-600 dark:text-zinc-400">{issue.recommendation}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  {/* Desktop Table View */}
                  <table className="hidden md:table w-full text-left text-sm text-slate-600 dark:text-zinc-400">
                    <thead className="text-xs uppercase bg-slate-50 dark:bg-zinc-800 text-slate-500 dark:text-zinc-300">
                      <tr>
                        <th className="px-4 py-3">Column</th>
                        <th className="px-4 py-3">Semantic Type</th>
                        <th className="px-4 py-3">Missing (Before → After)</th>
                        <th className="px-4 py-3">Outliers (Before → After)</th>
                        <th className="px-4 py-3">Strategy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.column_impacts?.map((imp, idx) => {
                        const sem = data.column_semantics?.[imp.column];
                        return (
                          <tr key={idx} className="border-b border-slate-100 dark:border-zinc-800">
                            <td className="px-4 py-3 font-semibold text-slate-900 dark:text-zinc-200">{imp.column}</td>
                            <td className="px-4 py-3">
                              <span className="font-medium text-slate-700 dark:text-zinc-300">{sem?.type || "Unknown"}</span>
                              {sem?.confidence !== undefined && (
                                <span className="text-[10px] text-slate-400 ml-1.5 font-bold font-mono">({Math.round(sem.confidence * 100)}%)</span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <span className={imp.missing_before > 0 ? "text-amber-500 font-bold" : "text-slate-400"}>{imp.missing_before}</span>
                              <span className="text-slate-400 mx-1">→</span>
                              <span className={imp.missing_after === 0 && imp.missing_before > 0 ? "text-emerald-500 font-bold" : "text-slate-700 dark:text-zinc-300"}>{imp.missing_after}</span>
                            </td>
                            <td className="px-4 py-3">
                              <span className={imp.outliers_before > 0 ? "text-amber-500 font-bold" : "text-slate-400"}>{imp.outliers_before}</span>
                              <span className="text-slate-400 mx-1">→</span>
                              <span className={imp.outliers_after === 0 && imp.outliers_before > 0 ? "text-emerald-500 font-bold" : "text-slate-700 dark:text-zinc-300"}>{imp.outliers_after}</span>
                            </td>
                            <td className="px-4 py-3 text-xs">
                              <span className="text-slate-500 font-medium">{sem?.strategy || "None"}</span>
                              {sem?.reason && sem.reason !== "No cleaning required based on data profile." && (
                                <span className="text-slate-400 block text-[10px] mt-0.5">{sem.reason}</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  {/* Mobile Stacked Card View */}
                  <div className="block md:hidden space-y-4">
                    {data.column_impacts?.map((imp, idx) => {
                      const sem = data.column_semantics?.[imp.column];
                      return (
                        <div key={idx} className="p-4 bg-slate-50 dark:bg-zinc-800 rounded-2xl border border-slate-200/50 dark:border-zinc-800 space-y-2">
                          <div className="flex justify-between items-start">
                            <div>
                              <span className="text-[10px] font-bold text-slate-400 uppercase block">Column</span>
                              <span className="text-sm font-bold text-slate-900 dark:text-zinc-100">{imp.column}</span>
                            </div>
                            <div className="text-right">
                              <span className="text-[10px] font-bold text-slate-400 uppercase block">Semantic Type</span>
                              <span className="text-sm font-medium text-slate-700 dark:text-zinc-300">
                                {sem?.type || "Unknown"}
                                {sem?.confidence !== undefined && (
                                  <span className="text-[10px] text-slate-400 ml-1 font-mono">({Math.round(sem.confidence * 100)}%)</span>
                                )}
                              </span>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-2 gap-2 py-1">
                            <div>
                              <span className="text-[10px] font-bold text-slate-400 uppercase block">Missing Cells</span>
                              <div className="text-xs">
                                <span className={imp.missing_before > 0 ? "text-amber-500 font-bold" : "text-slate-400"}>{imp.missing_before}</span>
                                <span className="text-slate-400 mx-1">→</span>
                                <span className={imp.missing_after === 0 && imp.missing_before > 0 ? "text-emerald-500 font-bold" : "text-slate-700 dark:text-zinc-300"}>{imp.missing_after}</span>
                              </div>
                            </div>
                            <div>
                              <span className="text-[10px] font-bold text-slate-400 uppercase block">Outliers</span>
                              <div className="text-xs">
                                <span className={imp.outliers_before > 0 ? "text-amber-500 font-bold" : "text-slate-400"}>{imp.outliers_before}</span>
                                <span className="text-slate-400 mx-1">→</span>
                                <span className={imp.outliers_after === 0 && imp.outliers_before > 0 ? "text-emerald-500 font-bold" : "text-slate-700 dark:text-zinc-300"}>{imp.outliers_after}</span>
                              </div>
                            </div>
                          </div>
                          
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase block">Strategy</span>
                            <span className="text-xs text-slate-500 font-medium">{sem?.strategy || "None"}</span>
                            {sem?.reason && sem.reason !== "No cleaning required based on data profile." && (
                              <p className="text-[10px] text-slate-400 mt-0.5 leading-relaxed">{sem.reason}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen flex-col items-center justify-center space-y-4 dark:bg-zinc-950">
        <div className="h-10 w-10 border-4 border-slate-200 dark:border-zinc-800 border-t-red-500 animate-spin rounded-full" />
        <span className="text-xs text-slate-500 font-bold uppercase tracking-wider animate-pulse">Loading dashboard...</span>
      </div>
    }>
      <ResultsContent />
    </Suspense>
  );
}
