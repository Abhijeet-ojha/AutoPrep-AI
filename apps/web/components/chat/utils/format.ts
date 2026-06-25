/**
 * Format timestamp string to local time (HH:MM:SS)
 */
export function formatTimeLabel(timestampStr?: string): string {
  if (!timestampStr) return "";
  try {
    const date = new Date(timestampStr);
    if (isNaN(date.getTime())) return "";
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return "";
  }
}

/**
 * Format performance latency block
 */
export function formatLatencyLabel(latencyMs?: number): string {
  if (latencyMs === undefined || latencyMs === null) return "";
  return `${(latencyMs / 1000).toFixed(2)}s`;
}
