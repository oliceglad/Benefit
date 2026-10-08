import { ApiError, type FieldIssue } from './api-error'
import { session, type SessionTokens } from '@/shared/session/session'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

const noRefreshPaths = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/verify-email',
  '/api/v1/auth/resend-code',
  '/api/v1/auth/refresh',
  '/api/v1/auth/logout',
  '/api/v1/auth/oauth/exchange',
])

type RefreshOperation = {
  revision: number
  promise: Promise<boolean>
}

let refreshOperation: RefreshOperation | null = null

type ErrorEnvelope = {
  error?: { code?: string; message?: string }
  detail?: Array<{ loc?: Array<string | number>; msg?: string }> | string
}

function toRequestUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  if (apiBaseUrl) return `${apiBaseUrl}${path}`
  return new URL(path, window.location.origin).toString()
}

function isRefreshable(path: string): boolean {
  return !noRefreshPaths.has(new URL(path, window.location.origin).pathname)
}

function parseRetryAfter(response: Response): number | null {
  const value = response.headers.get('Retry-After')
  if (!value) return null
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : null
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) return undefined
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) return response.json()
  if (contentType.startsWith('image/') || contentType.includes('application/pdf')) {
    return response.blob()
  }
  const text = await response.text()
  return text || undefined
}

function fieldIssuesFrom(payload: ErrorEnvelope): FieldIssue[] {
  if (!Array.isArray(payload.detail)) return []
  return payload.detail.map((issue) => ({
    field: (issue.loc ?? []).filter((part) => part !== 'body').join('.'),
    message: issue.msg ?? 'Некорректное значение',
  }))
}

async function toApiError(response: Response): Promise<ApiError> {
  let payload: ErrorEnvelope
  try {
    payload = (await parseBody(response)) as ErrorEnvelope
  } catch {
    payload = {}
  }
  const error = payload.error
  const detailMessage = typeof payload.detail === 'string' ? payload.detail : null
  return new ApiError({
    status: response.status,
    code: error?.code ?? `http_${response.status}`,
    message: error?.message ?? detailMessage ?? 'Не удалось выполнить запрос',
    retryAfterSeconds: parseRetryAfter(response),
    fieldIssues: fieldIssuesFrom(payload),
  })
}

function tokenResponse(value: unknown): SessionTokens | null {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  if (
    typeof record.access_token !== 'string' ||
    typeof record.refresh_token !== 'string' ||
    typeof record.expires_in !== 'number' ||
    typeof record.refresh_expires_in !== 'number'
  ) {
    return null
  }
  return {
    accessToken: record.access_token,
    refreshToken: record.refresh_token,
    expiresIn: record.expires_in,
    refreshExpiresIn: record.refresh_expires_in,
  }
}

async function refreshSession(): Promise<boolean> {
  const refreshToken = session.getSnapshot().tokens?.refreshToken
  if (!refreshToken) return false
  const revision = session.getRevision()
  if (refreshOperation?.revision === revision) return refreshOperation.promise

  const operation: RefreshOperation = { revision, promise: Promise.resolve(false) }
  operation.promise = (async () => {
    try {
      const response = await fetch(toRequestUrl('/api/v1/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!response.ok) return false
      const tokens = tokenResponse(await parseBody(response))
      if (!tokens) return false
      return session.replaceTokensIfCurrent(tokens, revision, refreshToken)
    } catch {
      return false
    } finally {
      if (refreshOperation === operation) refreshOperation = null
    }
  })()
  refreshOperation = operation

  const refreshed = await operation.promise
  if (!refreshed) session.clearIfCurrent(revision, refreshToken)
  return refreshed
}

async function execute(path: string, options: RequestInit, replayed: boolean): Promise<Response> {
  const headers = new Headers(options.headers)
  const accessToken = session.getSnapshot().tokens?.accessToken
  if (accessToken && isRefreshable(path)) headers.set('Authorization', `Bearer ${accessToken}`)

  const response = await fetch(toRequestUrl(path), { ...options, headers })
  if (response.status !== 401 || replayed || !isRefreshable(path) || !accessToken) {
    return response
  }

  if (!(await refreshSession())) return response
  return execute(path, options, true)
}

export async function orvalFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await execute(path, options, false)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError({
      status: 0,
      code: 'network_error',
      message: 'Нет соединения с сервером. Проверьте сеть и попробуйте ещё раз.',
    })
  }
  if (!response.ok) throw await toApiError(response)
  return {
    data: await parseBody(response),
    status: response.status,
    headers: response.headers,
  } as T
}

export type ErrorType<Error> = ApiError & { response?: Error }
export type BodyType<BodyData> = BodyData

export const transportTestApi = {
  reset(): void {
    refreshOperation = null
    session.clear()
  },
}
