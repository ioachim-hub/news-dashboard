/**
 * Compact recommendation labels for the Today feed.
 *
 * The backend exposes a per-user `recommendation_score` (0–100) blended from
 * behavioral affinity, semantic similarity, freshness, and novelty. We collapse
 * that continuous score into three scannable bands so a ranked feed stays
 * readable without surfacing raw numbers. When no score is available (the user
 * has no recommendation metadata for an article yet) the helper returns `null`,
 * and callers fall back to the existing importance-derived visual signal.
 */

export type RecommendationLabel = 'recommended' | 'relevant' | 'low';

// Band thresholds on the 0–100 recommendation score. Tuned so "Recommended" is
// reserved for genuinely strong matches while most ranked items read "Relevant".
const RECOMMENDED_THRESHOLD = 70;
const RELEVANT_THRESHOLD = 45;

export function recommendationLabel(score: number | null | undefined): RecommendationLabel | null {
  if (score == null || Number.isNaN(score)) return null;
  if (score >= RECOMMENDED_THRESHOLD) return 'recommended';
  if (score >= RELEVANT_THRESHOLD) return 'relevant';
  return 'low';
}

export const RECOMMENDATION_LABEL_TEXT: Record<RecommendationLabel, string> = {
  recommended: 'Recommended',
  relevant: 'Relevant',
  low: 'Low signal',
};
