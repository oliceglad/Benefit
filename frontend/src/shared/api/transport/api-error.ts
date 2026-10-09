export type FieldIssue = {
  field: string
  message: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryAfterSeconds: number | null
  readonly fieldIssues: FieldIssue[]
  readonly service: string | null
  readonly requestId: string | null

  constructor({
    status,
    code,
    message,
    retryAfterSeconds = null,
    fieldIssues = [],
    service = null,
    requestId = null,
  }: {
    status: number
    code: string
    message: string
    retryAfterSeconds?: number | null
    fieldIssues?: FieldIssue[]
    service?: string | null
    requestId?: string | null
  }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
    this.fieldIssues = fieldIssues
    this.service = service
    this.requestId = requestId
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}
