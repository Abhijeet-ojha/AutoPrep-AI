/**
 * Utility to buffer and sanitize incomplete markdown formatting blocks
 * during token-aware active streaming to ensure rendering stability.
 */
export function sanitizeStreamingMarkdown(text: string): string {
  if (!text) return "";

  // 1. Buffer Code Fences:
  // If we have an odd number of code blocks, we temporarily slice the text 
  // to the beginning of the open code block to hide it until it's finished.
  const fenceCount = (text.match(/```/g) || []).length;
  if (fenceCount % 2 !== 0) {
    const lastIdx = text.lastIndexOf("```");
    if (lastIdx !== -1) {
      return text.substring(0, lastIdx);
    }
  }

  // 2. Buffer Inline Code:
  // If there's an odd number of single backticks, slice before the last backtick.
  const inlineTickCount = (text.match(/`/g) || []).length;
  if (inlineTickCount % 2 !== 0) {
    const lastIdx = text.lastIndexOf("`");
    if (lastIdx !== -1) {
      return text.substring(0, lastIdx);
    }
  }

  // 3. Buffer Bold/Italic Markers:
  // If text ends with incomplete bold/italic formatting, slice it off.
  if (text.endsWith("**") || text.endsWith("__")) {
    return text.slice(0, -2);
  }
  if (text.endsWith("*") || text.endsWith("_")) {
    return text.slice(0, -1);
  }

  // 4. Buffer Incomplete Tables:
  // If we are currently inside a table line (contains |) but the row is not completed 
  // (does not end with pipe followed by newline, or doesn't have trailing pipe).
  const lastLineIdx = text.lastIndexOf("\n");
  const lastLine = lastLineIdx !== -1 ? text.substring(lastLineIdx + 1) : text;
  if (lastLine.includes("|")) {
    // If it doesn't end with a pipe, buffer the entire last line
    if (!lastLine.trim().endsWith("|")) {
      return lastLineIdx !== -1 ? text.substring(0, lastLineIdx) : "";
    }
  }

  // 5. Buffer Incomplete Lists:
  // If the last line contains only list bullets or numbers.
  if (
    lastLine.trim() === "-" ||
    lastLine.trim() === "*" ||
    lastLine.trim() === "+" ||
    /^\d+\.$/.test(lastLine.trim()) ||
    /^\d+\.\s*$/.test(lastLine.trim())
  ) {
    return lastLineIdx !== -1 ? text.substring(0, lastLineIdx) : "";
  }

  // 6. Buffer Blockquotes:
  // If the last line starts with > but has no content yet.
  if (lastLine.trim() === ">") {
    return lastLineIdx !== -1 ? text.substring(0, lastLineIdx) : "";
  }

  return text;
}
