"use client";

import { useState, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { uploadDataset } from "@/lib/api";
import { UploadCloud, AlertCircle, FileSpreadsheet, ShieldCheck } from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDrag = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    setError(null);
    const filename = selectedFile.name;
    const extension = filename.split(".").pop()?.toLowerCase();
    
    // Validate CSV extension
    if (extension !== "csv") {
      setError("Invalid CSV format. Please upload a CSV file only.");
      setFile(null);
      return;
    }
    
    // Validate size <= 100MB
    if (selectedFile.size > 100 * 1024 * 1024) {
      setError("File too large. Maximum size is 100MB.");
      setFile(null);
      return;
    }
    
    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadDataset(file);
      
      // Store credentials in sessionStorage
      sessionStorage.setItem("autoprep_session_id", data.dataset_summary.dataset_id);
      sessionStorage.setItem("autoprep_session_token", data.session_token);
      sessionStorage.setItem("autoprep_results", JSON.stringify(data));
      
      router.push(`/results?session_id=${data.dataset_summary.dataset_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload and analysis failed. Please verify your file or try again.");
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="relative h-screen overflow-hidden flex flex-col items-center justify-center bg-zinc-950 px-4 text-zinc-50">
        {/* Background Ambient Glows */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-red-500/[0.03] blur-[150px] pointer-events-none" />
        <div className="flex flex-col items-center space-y-6 max-w-md text-center z-10">
          <div className="relative flex h-20 w-20 items-center justify-center">
            <div className="absolute h-full w-full rounded-full border-4 border-zinc-800" />
            <div className="absolute h-full w-full rounded-full border-4 border-t-red-500 animate-spin" />
            <FileSpreadsheet className="h-8 w-8 text-red-500 animate-pulse" />
          </div>
          
          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight text-zinc-50">
              Uploading & Analyzing Dataset...
            </h2>
            <p className="text-sm text-zinc-400 font-medium">
              This may take a few seconds for large datasets.
            </p>
          </div>

          <div className="w-full bg-zinc-800 h-1 rounded-full overflow-hidden">
            <div className="bg-red-500 h-1 animate-pulse" style={{ width: '100%' }} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-screen overflow-hidden flex flex-col items-center justify-center bg-zinc-950 text-zinc-50 px-4">
      {/* Background Ambient Glows */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-red-500/[0.04] blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 rounded-full bg-cyan-500/[0.03] blur-[120px] pointer-events-none" />
      {/* Main Content */}
      <main className="flex flex-col items-center justify-center max-w-xl w-full space-y-8 animate-fade-in z-10">
        {/* Hero Section */}
        <div className="space-y-4 text-center">
          <h1 className="title text-5xl font-extrabold tracking-tight sm:text-6xl bg-gradient-to-r from-zinc-50 via-zinc-200 to-red-500 bg-clip-text text-transparent select-none">
            AutoPrep AI
          </h1>
          <p className="title text-lg font-semibold text-zinc-200 sm:text-xl leading-tight">
            Get cleaned datasets and actionable insights in seconds.
          </p>
          <div className="text-zinc-400 text-xs sm:text-sm space-y-1">
            <p>Privacy-first dataset cleaning and analysis.</p>
            <p>Your files are processed temporarily in memory and permanently removed after download.</p>
          </div>
        </div>

        {/* Drag & Drop Area */}
        <div className="w-full">
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 transition-all cursor-pointer ${
              dragActive
                ? "border-red-500 bg-red-950/10"
                : "border-zinc-700 bg-zinc-900/80 hover:border-zinc-600"
            } shadow-lg shadow-black/20 backdrop-blur`}
          >
            <input
              type="file"
              accept=".csv"
              onChange={handleChange}
              className="absolute inset-0 w-full h-full cursor-pointer opacity-0"
              id="csv-file-input"
            />
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-800 text-zinc-400 shadow-inner">
                {file ? (
                  <FileSpreadsheet className="h-7 w-7 text-emerald-500 animate-bounce" />
                ) : (
                  <UploadCloud className="h-7 w-7 text-zinc-500" />
                )}
              </div>
              <div className="space-y-1">
                <p className="text-base font-bold text-zinc-200">
                  {file ? file.name : "Drag & drop your CSV here"}
                </p>
                <p className="text-xs text-zinc-500 font-semibold">
                  {file ? `File Size: ${(file.size / 1024 / 1024).toFixed(2)} MB` : "or browse files (maximum size: 100MB)"}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 space-y-4">
            {file && (
              <button
                onClick={handleUpload}
                className="w-full rounded-xl bg-zinc-50 text-center py-4 text-sm font-extrabold text-zinc-950 shadow-xl hover:bg-zinc-200 transition-all focus:ring-2 focus:ring-slate-500 focus:outline-none"
              >
                Clean & Generate Insights ✦
              </button>
            )}

            {error && (
              <div className="flex items-start gap-3 text-left text-sm font-semibold text-red-400 bg-red-950/20 border border-red-900/30 p-4 rounded-xl shadow-sm animate-fade-in">
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Verification Error</p>
                  <p className="text-xs text-zinc-400 mt-0.5">{error}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
