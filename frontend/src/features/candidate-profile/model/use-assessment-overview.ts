import { useQueries, useQuery } from '@tanstack/react-query'

import {
  assessmentAttemptQueryKey,
  assessmentCatalogQueryKey,
  assessmentHistoryQueryKey,
  assessmentStatusQueryKey,
  getAssessmentAttempt,
  getAssessmentCatalog,
  getAssessmentHistory,
  getAssessmentStatus,
} from '@/features/candidate-profile/api/assessment'
import type { AttemptResponse } from '@/shared/api/generated/assessments/models'

export function useAssessmentOverview() {
  const catalog = useQuery({
    queryKey: assessmentCatalogQueryKey,
    queryFn: ({ signal }) => getAssessmentCatalog(signal),
    staleTime: 5 * 60_000,
  })
  const status = useQuery({
    queryKey: assessmentStatusQueryKey,
    queryFn: ({ signal }) => getAssessmentStatus(signal),
    staleTime: 30_000,
  })
  const history = useQuery({
    queryKey: assessmentHistoryQueryKey,
    queryFn: ({ signal }) => getAssessmentHistory(signal),
    staleTime: 30_000,
  })
  const ids = new Set<string>()
  if (status.data?.active_attempt_id) ids.add(status.data.active_attempt_id)
  history.data
    ?.filter((attempt) => !attempt.assignment_id)
    .slice(0, 5)
    .forEach((attempt) => ids.add(attempt.id))
  const attemptIds = [...ids]
  const attemptQueries = useQueries({
    queries: attemptIds.map((attemptId) => ({
      queryKey: assessmentAttemptQueryKey(attemptId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getAssessmentAttempt(attemptId, signal),
      staleTime: 30_000,
    })),
  })
  const attempts: AttemptResponse[] = attemptQueries.flatMap((query) => query.data ? [query.data] : [])

  return {
    catalog: catalog.data ?? [],
    status: status.data ?? null,
    attempts,
    loading: catalog.isPending || status.isPending || history.isPending || attemptQueries.some((query) => query.isPending),
    failed: catalog.isError || status.isError,
    resultFailed: history.isError || attemptQueries.some((query) => query.isError),
  }
}
