import { Message } from "../types";

/**
 * Renders conversation logs into styled Markdown format, including metadata blocks.
 */
export function formatConversationMarkdown(
  messages: Message[],
  metadata: {
    filename?: string;
    rows?: number;
    columns?: number;
    health_score?: number;
    ml_readiness?: number;
    upload_time?: string;
  } = {}
): string {
  let md = "";
  
  // Header section
  md += `# AutoPrep AI Copilot Analysis Report\n\n`;
  md += `## Session Metadata\n`;
  md += `- **Dataset File**: ${metadata.filename || "unknown"}\n`;
  md += `- **Dimensions**: ${metadata.rows || 0} rows x ${metadata.columns || 0} columns\n`;
  md += `- **Overall Health Score**: ${metadata.health_score ?? 100}/100\n`;
  md += `- **ML Readiness Score**: ${metadata.ml_readiness ?? 50}/100\n`;
  md += `- **Export Date**: ${new Date().toISOString().replace("T", " ").substring(0, 19)} UTC\n\n`;
  md += `---\n\n`;

  // Message Logs
  messages.forEach((msg, idx) => {
    const roleName = msg.role === "user" ? "User Query" : "Dataset Copilot";
    const ts = msg.metadata?.timestamp
      ? ` (${msg.metadata.timestamp.substring(11, 19)})`
      : "";
    const modelUsed = msg.metadata?.model_used
      ? ` [Model: ${msg.metadata.model_used} via ${msg.metadata.provider_used}]`
      : "";

    md += `### 💬 ${roleName}${ts}${modelUsed}\n\n`;
    md += `${msg.message}\n\n`;
    
    if (idx < messages.length - 1) {
      md += `\n---\n\n`;
    }
  });

  return md;
}
