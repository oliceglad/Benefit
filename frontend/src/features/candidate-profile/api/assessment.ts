import {
  answerApiV1AssessmentsAttemptsAttemptIdAnswersPost,
  assessmentStatusApiV1AssessmentsStatusGet,
  currentTaskApiV1AssessmentsAttemptsAttemptIdCurrentTaskGet,
  finishApiV1AssessmentsAttemptsAttemptIdFinishPost,
  getAttemptApiV1AssessmentsAttemptsAttemptIdGet,
  historyApiV1AssessmentsAttemptsGet,
  listTestsApiV1AssessmentsTestsGet,
  startAttemptApiV1AssessmentsAttemptsPost,
  surveyApiV1AssessmentsSurveyGet,
} from '@/shared/api/generated/assessments/assessments'
import type {
  AnswerRequest,
  AnswerResponse,
  AssessmentInfo,
  AssessmentStatus,
  AttemptResponse,
  AttemptSummary,
  SurveyAnswers,
  SurveyOptions,
  TaskView,
} from '@/shared/api/generated/assessments/models'

export const assessmentCatalogQueryKey = ['candidate', 'assessment', 'catalog'] as const
export const assessmentSurveyQueryKey = ['candidate', 'assessment', 'survey'] as const
export const assessmentStatusQueryKey = ['candidate', 'assessment', 'status'] as const
export const assessmentHistoryQueryKey = ['candidate', 'assessment', 'history'] as const
export const assessmentAttemptQueryKey = (attemptId: string) => ['candidate', 'assessment', 'attempt', attemptId] as const
export const assessmentTaskQueryKey = (attemptId: string) => ['candidate', 'assessment', 'task', attemptId] as const

export async function getAssessmentCatalog(signal?: AbortSignal): Promise<AssessmentInfo[]> {
  const response = await listTestsApiV1AssessmentsTestsGet({ signal })
  return response.data
}

export async function getAssessmentSurvey(signal?: AbortSignal): Promise<SurveyOptions> {
  const response = await surveyApiV1AssessmentsSurveyGet({ signal })
  return response.data
}

export async function getAssessmentStatus(signal?: AbortSignal): Promise<AssessmentStatus> {
  const response = await assessmentStatusApiV1AssessmentsStatusGet({ signal })
  return response.data
}

export async function getAssessmentHistory(signal?: AbortSignal): Promise<AttemptSummary[]> {
  const response = await historyApiV1AssessmentsAttemptsGet({ signal })
  return response.data
}

export async function startAssessment(values: SurveyAnswers): Promise<AttemptResponse> {
  const response = await startAttemptApiV1AssessmentsAttemptsPost(values)
  if (response.status !== 201) throw new Error('Assessment start returned an unexpected status')
  return response.data
}

export async function getAssessmentAttempt(attemptId: string, signal?: AbortSignal): Promise<AttemptResponse> {
  const response = await getAttemptApiV1AssessmentsAttemptsAttemptIdGet(attemptId, { signal })
  if (response.status !== 200) throw new Error('Assessment attempt returned an unexpected status')
  return response.data
}

export async function getAssessmentTask(attemptId: string, signal?: AbortSignal): Promise<TaskView> {
  const response = await currentTaskApiV1AssessmentsAttemptsAttemptIdCurrentTaskGet(attemptId, { signal })
  if (response.status !== 200) throw new Error('Assessment task returned an unexpected status')
  return response.data
}

export async function submitAssessmentAnswer(attemptId: string, answer: AnswerRequest): Promise<AnswerResponse> {
  const response = await answerApiV1AssessmentsAttemptsAttemptIdAnswersPost(attemptId, answer)
  if (response.status !== 200) throw new Error('Assessment answer returned an unexpected status')
  return response.data
}

export async function finishAssessment(attemptId: string): Promise<AttemptResponse> {
  const response = await finishApiV1AssessmentsAttemptsAttemptIdFinishPost(attemptId)
  if (response.status !== 200) throw new Error('Assessment finish returned an unexpected status')
  return response.data
}
