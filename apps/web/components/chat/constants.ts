export const CHAT_LIMITS = {
  maxMessages: 100,
  maxSuggestions: 4,
  maxInputLines: 6,
};

export const STREAMING_SPEEDS = {
  normalSpeed: 2,       // characters/ticks or chunks consumed per frame
  catchUpSpeed: 10,
  flushSpeed: 40,
  queueThresholdNormal: 50,
  queueThresholdCatchUp: 200,
};

export const TIMINGS = {
  searchDebounceMs: 150,
  chipTransitionMs: 200,
  copyFeedbackMs: 2000,
  pulseAnimationMs: 650,
  expandedTransitionMs: 250,
};

export const EXPORTS = {
  defaultFilename: "conversation_report",
  mdExtension: ".md",
  pdfExtension: ".pdf",
};
