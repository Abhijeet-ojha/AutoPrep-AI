import { useCallback, useState } from "react";
import { Message } from "../types";
import { formatConversationMarkdown } from "../utils/exports";
import { getSessionToken, API_BASE } from "@/lib/api";

export function useChatExport(datasetId: string, messages: Message[], datasetMetadata: any = {}) {
  const [isExporting, setIsExporting] = useState(false);

  const exportMarkdown = useCallback((msgOnly?: Message) => {
    let content = "";
    let filename = "";

    if (msgOnly) {
      content = `# AutoPrep AI Copilot Response\n\n${msgOnly.message}\n`;
      filename = `autoprep_copilot_response_${datasetId}.md`;
    } else {
      content = formatConversationMarkdown(messages, {
        filename: datasetMetadata.filename || "dataset.csv",
        rows: datasetMetadata.rows || 0,
        columns: datasetMetadata.columns || 0,
        health_score: datasetMetadata.health_score || 100,
        ml_readiness: datasetMetadata.readiness?.score || 50,
      });
      filename = `autoprep_conversation_log_${datasetId}.md`;
    }

    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }, [datasetId, messages, datasetMetadata]);

  const exportPDF = useCallback(async (msgOnly?: Message) => {
    setIsExporting(true);
    try {
      const token = getSessionToken();
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (token) {
        headers["X-Session-Token"] = token;
      }

      const body = msgOnly 
        ? { message_id: msgOnly.id }
        : { messages: messages };

      const res = await fetch(`${API_BASE}/datasets/${datasetId}/copilot/export_pdf`, {
        method: "POST",
        headers,
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = msgOnly 
        ? `copilot_response_${datasetId}.pdf`
        : `copilot_conversation_${datasetId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF export failed:", err);
      alert("Failed to export chat to PDF.");
    } finally {
      setIsExporting(false);
    }
  }, [datasetId, messages]);

  return {
    exportMarkdown,
    exportPDF,
    isExporting,
  };
}
