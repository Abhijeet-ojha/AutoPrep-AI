/**
 * Pure functions to manipulate character/token queues.
 */
export function enqueueTokens(queue: string[], chunk: string): string[] {
  if (!chunk) return queue;
  // Gemini or Groq yields words or pieces of words. We treat them as tokens.
  return [...queue, chunk];
}

export function dequeueTokens(queue: string[], count: number): { items: string[]; remaining: string[] } {
  const items = queue.slice(0, count);
  const remaining = queue.slice(count);
  return { items, remaining };
}
