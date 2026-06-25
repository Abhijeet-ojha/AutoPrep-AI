/**
 * Calculates if scroll height is close enough to viewport bounds to follow automatically.
 */
export function isNearBottomBoundary(element: HTMLDivElement | null, threshold: number = 40): boolean {
  if (!element) return true;
  const offset = element.scrollHeight - element.scrollTop - element.clientHeight;
  return offset <= threshold;
}

/**
 * Scroll smoothly to the bottom.
 */
export function scrollToBottom(element: HTMLDivElement | null, smooth: boolean = true) {
  if (!element) return;
  element.scrollTo({
    top: element.scrollHeight,
    behavior: smooth ? "smooth" : "auto"
  });
}
