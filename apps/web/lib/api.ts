export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function getSessionToken(): string | null {
  if (typeof window !== "undefined") {
    return sessionStorage.getItem("autoprep_session_token");
  }
  return null;
}

export async function uploadDataset(file: File) {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/datasets/upload`, {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function getJSON(path: string) {
  const token = getSessionToken();
  const headers: HeadersInit = {};
  if (token) {
    headers["X-Session-Token"] = token;
  }
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function postJSON(path: string, body: unknown) {
  const token = getSessionToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["X-Session-Token"] = token;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function downloadCleanedCSV(sessionId: string, filename: string) {
  const token = getSessionToken();
  const headers: HeadersInit = {};
  if (token) {
    headers["X-Session-Token"] = token;
  }
  const res = await fetch(`${API_BASE}/datasets/${sessionId}/download`, { headers });
  if (!res.ok) {
    const errText = await res.text();
    let message = "Failed to download cleaned dataset.";
    try {
      const parsed = JSON.parse(errText);
      if (parsed.detail) message = parsed.detail;
    } catch {
      if (errText) message = errText;
    }
    throw new Error(message);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename.replace(".csv", "")}_cleaned.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 250);
}

export async function downloadReport(sessionId: string) {
  const token = getSessionToken();
  const headers: HeadersInit = {};
  if (token) {
    headers["X-Session-Token"] = token;
  }
  const res = await fetch(`${API_BASE}/datasets/${sessionId}/report`, { headers });
  if (!res.ok) {
    const errText = await res.text();
    let message = "Failed to retrieve cleaning report.";
    try {
      const parsed = JSON.parse(errText);
      if (parsed.detail) message = parsed.detail;
    } catch {
      if (errText) message = errText;
    }
    throw new Error(message);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `report_${sessionId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 250);
}

export async function downloadCleaningLog(sessionId: string) {
  const token = getSessionToken();
  const headers: HeadersInit = {};
  if (token) {
    headers["X-Session-Token"] = token;
  }
  const res = await fetch(`${API_BASE}/datasets/${sessionId}/download_log`, { headers });
  if (!res.ok) {
    const errText = await res.text();
    let message = "Failed to download cleaning log.";
    try {
      const parsed = JSON.parse(errText);
      if (parsed.detail) message = parsed.detail;
    } catch {
      if (errText) message = errText;
    }
    throw new Error(message);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `cleaning_log_${sessionId}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 250);
}

export async function postJSONStream(
  path: string,
  body: unknown,
  onMessage: (data: any) => void,
  signal?: AbortSignal
) {
  const token = getSessionToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["X-Session-Token"] = token;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("ReadableStream not supported in this browser.");
  }
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done && !buffer) break;
    
    if (value) {
      buffer += decoder.decode(value, { stream: true });
    }
    
    let boundary = buffer.indexOf("\n");
    while (boundary !== -1) {
      const line = buffer.substring(0, boundary).trim();
      buffer = buffer.substring(boundary + 1);
      if (line) {
        try {
          const parsed = JSON.parse(line);
          onMessage(parsed);
        } catch (e) {
          console.error("Failed to parse NDJSON line:", line, e);
        }
      }
      boundary = buffer.indexOf("\n");
    }
    if (done) break;
  }
}


