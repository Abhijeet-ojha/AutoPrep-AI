"use client";

import { FormEvent, useState } from "react";

import { postJSON } from "@/lib/api";

export function ChatPanel({ datasetId }: { datasetId: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const ask = async (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    try {
      const data = await postJSON(`/datasets/${datasetId}/chat`, { question });
      setAnswer(data.answer);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3 className="title text-xl font-semibold">Dataset Chatbot</h3>
      <form onSubmit={ask} className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask: Why median for Age?"
          className="w-full rounded-lg border border-slate-300 px-3 py-2"
        />
        <button className="rounded-lg bg-cyan-500 px-4 py-2 text-white">{loading ? "..." : "Ask"}</button>
      </form>
      {answer && <p className="mt-3 text-sm text-slate-700">{answer}</p>}
    </div>
  );
}
