export type FieldIssue = {
  field: string
  message: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryAfterSeconds: number | null
  readonly fieldIssues: FieldIssue[]

  constructor({
    status,
    code,
    message,
    retryAfterSeconds = null,
    fieldIssues = [],
  }: {
    status: number
    code: string
    message: string
    retryAfterSeconds?: number | null
    fieldIssues?: FieldIssue[]
  }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
    this.fieldIssues = fieldIssues
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}
