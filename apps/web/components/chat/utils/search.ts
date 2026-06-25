/**
 * Escape special regex characters.
 */
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Pure search match index calculations.
 * Supports partial-matching, case-insensitive, and whole-word queries.
 */
export function findSearchMatches(
  text: string,
  query: string,
  options: { caseSensitive?: boolean; wholeWord?: boolean } = {}
): RegExpMatchArray | null {
  if (!query || !text) return null;

  const escapedQuery = escapeRegExp(query);
  const flags = options.caseSensitive ? "g" : "gi";
  
  // Construct whole-word boundaries or standard regex matches
  const pattern = options.wholeWord 
    ? `\\b${escapedQuery}\\b` 
    : escapedQuery;

  try {
    const regex = new RegExp(pattern, flags);
    return text.match(regex);
  } catch {
    return null;
  }
}

/**
 * Highlight matched terms by splitting text.
 */
export function getSearchMatchParts(text: string, query: string, wholeWord: boolean = false): string[] {
  if (!query) return [text];
  const escapedQuery = escapeRegExp(query);
  const pattern = wholeWord ? `\\b(${escapedQuery})\\b` : `(${escapedQuery})`;
  return text.split(new RegExp(pattern, "gi"));
}
