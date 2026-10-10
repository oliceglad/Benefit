import { ApiError, type FieldIssue } from './api-error'
import { session } from '@/shared/session/session'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''
const csrfCookieName = 'benefit_csrf'

const noRefreshPaths = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/verify-email',
  '/api/v1/auth/resend-code',
  '/api/v1/auth/refresh',
  '/api/v1/auth/logout',
  '/api/v1/auth/oauth/exchange',
])

const cookieDeliveryPaths = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/verify-email',
  '/api/v1/auth/refresh',
  '/api/v1/auth/oauth/exchange',
])

type RefreshOperation = {
  revision: number
  promise: Promise<boolean>
}

type ErrorDetail = { field?: string; message?: string }
type ErrorEnvelope = {
  error?: {
    code?: string
    message?: string
    service?: string
    request_id?: string
    details?: ErrorDetail[]
  }
  detail?: Array<{ loc?: Array<string | number>; msg?: string }> | string
}

let refreshOperation: RefreshOperation | null = null

function toRequestUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  if (apiBaseUrl) return `${apiBaseUrl}${path}`
  return new URL(path, window.location.origin).toString()
}

function requestPath(path: string): string {
  return new URL(path, window.location.origin).pathname
}

function isRefreshable(path: string): boolean {
  return !noRefreshPaths.has(requestPath(path))
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
  if (Array.isArray(payload.error?.details)) {
    return payload.error.details
      .filter((issue) => typeof issue.field === 'string' && typeof issue.message === 'string')
      .map((issue) => ({ field: issue.field as string, message: issue.message as string }))
  }
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
    service: error?.service ?? null,
    requestId: error?.request_id ?? null,
  })
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const prefix = `${encodeURIComponent(name)}=`
  const part = document.cookie.split('; ').find((item) => item.startsWith(prefix))
  if (!part) return null
  try {
    return decodeURIComponent(part.slice(prefix.length))
  } catch {
    return null
  }
}

function prepareHeaders(path: string, method: string, source?: HeadersInit): Headers {
  const headers = new Headers(source)
  const pathname = requestPath(path)
  if (cookieDeliveryPaths.has(pathname)) headers.set('X-Auth-Mode', 'cookie')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) {
    const csrfToken = readCookie(csrfCookieName)
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  }
  return headers
}

function isCookieDelivery(value: unknown): boolean {
  return Boolean(value && typeof value === 'object' && (value as Record<string, unknown>).delivery === 'cookie')
}

async function refreshSession(): Promise<boolean> {
  if (session.getSnapshot().status === 'anonymous') return false
  const revision = session.getRevision()
  if (refreshOperation?.revision === revision) return refreshOperation.promise

  const operation: RefreshOperation = { revision, promise: Promise.resolve(false) }
  operation.promise = (async () => {
    try {
      const path = '/api/v1/auth/refresh'
      const response = await fetch(toRequestUrl(path), {
        method: 'POST',
        credentials: 'include',
        headers: prepareHeaders(path, 'POST'),
      })
      if (!response.ok) return false
      return isCookieDelivery(await parseBody(response)) && session.isRevisionCurrent(revision)
    } catch {
      return false
    } finally {
      if (refreshOperation === operation) refreshOperation = null
    }
  })()
  refreshOperation = operation

  const refreshed = await operation.promise
  if (!refreshed) session.setAnonymousIfCurrent(revision)
  return refreshed
}

async function execute(path: string, options: RequestInit, replayed: boolean): Promise<Response> {
  const method = options.method ?? 'GET'
  const headers = prepareHeaders(path, method, options.headers)
  const response = await fetch(toRequestUrl(path), {
    ...options,
    headers,
    credentials: 'include',
  })
  if (
    response.status !== 401 ||
    replayed ||
    !isRefreshable(path) ||
    session.getSnapshot().status === 'anonymous'
  ) {
    return response
  }

  if (!(await refreshSession())) return response
  return execute(path, options, true)
}

export async function invalidateSessionForLogout(): Promise<void> {
  session.setAnonymous()
  const pendingRefresh = refreshOperation?.promise
  if (pendingRefresh) await pendingRefresh
}

export async function orvalFetch<T>(path: string, options: RequestInit & { responseType?: 'blob' } = {}): Promise<T> {
  const { responseType, ...fetchOptions } = options
  let response: Response
  try {
    response = await execute(path, fetchOptions, false)
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
    data: responseType === 'blob' ? await response.blob() : await parseBody(response),
    status: response.status,
    headers: response.headers,
  } as T
}

export type ErrorType<Error> = ApiError & { response?: Error }
export type BodyType<BodyData> = BodyData

export const transportTestApi = {
  reset(): void {
    refreshOperation = null
    session.reset()
  },
}
