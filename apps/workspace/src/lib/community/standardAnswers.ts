/**
 * Community build: standard answers are not available. Returns an empty,
 * non-loading result so callers render without them.
 */
export function useStandardAnswerCategories() {
  return {
    data: undefined as never[] | undefined,
    isLoading: false,
    error: undefined as Error | undefined,
  };
}
