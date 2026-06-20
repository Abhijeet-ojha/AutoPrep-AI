"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { uploadDataset } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadDataset(file);
      localStorage.setItem("autoprep_dataset_id", data.dataset_id);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="space-y-4">
      <h1 className="title text-3xl font-bold">Dataset Ingestion</h1>
      <div className="card space-y-4">
        <p className="text-slate-600">Supported formats: CSV, XLSX, JSON</p>
        <input
          type="file"
          accept=".csv,.xlsx,.json"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full rounded-lg border border-slate-300 p-2"
        />
        <button
          onClick={onUpload}
          disabled={!file || loading}
          className="rounded-xl bg-red-500 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "Uploading..." : "Upload and Analyze"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </main>
  );
}
