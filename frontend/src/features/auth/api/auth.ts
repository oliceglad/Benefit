import {
  loginApiV1AuthLoginPost,
  logoutApiV1AuthLogoutPost,
  meApiV1UsersMeGet,
  registerApiV1AuthRegisterPost,
  resendCodeApiV1AuthResendCodePost,
  verifyEmailApiV1AuthVerifyEmailPost,
} from '@/shared/api/generated/auth/auth'
import type {
  LoginRequest,
  RegisterResponse,
  TokenResponse,
} from '@/shared/api/generated/auth/models'
import { ApiError, isApiError } from '@/shared/api/transport/api-error'
import { invalidateSessionForLogout } from '@/shared/api/transport/orval-fetch'
import { session, type SessionUser } from '@/shared/session/session'

type RegisterCandidateInput = {
  email: string
  password: string
  fullName?: string
}

let restoreOperation: Promise<boolean> | null = null

function candidateUser(user: {
  id: string
  email: string
  role: string
  full_name?: string | null
  is_email_verified: boolean
}): SessionUser {
  if (user.role !== 'candidate') {
    throw new ApiError({
      status: 403,
      code: 'candidate_access_required',
      message: 'Этот кабинет доступен только пользователям с ролью кандидата.',
    })
  }
  return {
    id: user.id,
    email: user.email,
    role: user.role,
    fullName: user.full_name,
    isEmailVerified: user.is_email_verified,
  }
}

async function loadCurrentCandidate(revision: number): Promise<boolean> {
  const { data: user } = await meApiV1UsersMeGet()
  if (!session.isRevisionCurrent(revision)) return false
  session.setAuthenticated(candidateUser(user))
  return true
}

async function clearServerSession(): Promise<void> {
  try {
    await logoutApiV1AuthLogoutPost()
  } catch {
    // The local session still stays closed. A later reload will retry the server cookie.
  }
}

async function establishCandidateSession(tokenData: TokenResponse): Promise<void> {
  if (tokenData.delivery !== 'cookie') {
    throw new ApiError({
      status: 502,
      code: 'cookie_session_not_established',
      message: 'Сервер не создал защищённую сессию. Попробуйте войти ещё раз.',
    })
  }

  const revision = session.getRevision()
  try {
    if (!(await loadCurrentCandidate(revision))) {
      throw new ApiError({
        status: 401,
        code: 'session_changed',
        message: 'Сессия была изменена. Повторите вход.',
      })
    }
  } catch (error) {
    session.setAnonymousIfCurrent(revision)
    await clearServerSession()
    throw error
  }
}

export async function restoreCandidateSession(): Promise<boolean> {
  const snapshot = session.getSnapshot()
  if (snapshot.status === 'authenticated') return true
  if (snapshot.status === 'anonymous') return false
  if (restoreOperation) return restoreOperation

  const revision = session.getRevision()
  const operation = (async () => {
    try {
      return await loadCurrentCandidate(revision)
    } catch (error) {
      session.setAnonymousIfCurrent(revision)
      if (isApiError(error) && (error.status === 401 || error.code === 'candidate_access_required')) {
        if (error.code === 'candidate_access_required') await clearServerSession()
        return false
      }
      throw error
    } finally {
      restoreOperation = null
    }
  })()
  restoreOperation = operation
  return operation
}

export async function loginCandidate(credentials: LoginRequest): Promise<void> {
  session.setUnknown()
  try {
    const tokenResponse = await loginApiV1AuthLoginPost(credentials)
    if (tokenResponse.status !== 200) {
      throw new ApiError({ status: tokenResponse.status, code: 'login_failed', message: 'Не удалось войти.' })
    }
    await establishCandidateSession(tokenResponse.data)
  } catch (error) {
    session.setAnonymous()
    throw error
  }
}

export async function registerCandidate(input: RegisterCandidateInput): Promise<RegisterResponse> {
  const response = await registerApiV1AuthRegisterPost({
    email: input.email,
    password: input.password,
    role: 'candidate',
    full_name: input.fullName || null,
  })
  if (response.status !== 201) {
    throw new ApiError({
      status: response.status,
      code: 'registration_failed',
      message: 'Не удалось создать аккаунт.',
    })
  }
  return response.data
}

export async function verifyCandidateEmail(email: string, code: string): Promise<void> {
  session.setUnknown()
  try {
    const response = await verifyEmailApiV1AuthVerifyEmailPost({ email, code })
    if (response.status !== 200) {
      throw new ApiError({
        status: response.status,
        code: 'verification_failed',
        message: 'Не удалось подтвердить почту.',
      })
    }
    await establishCandidateSession(response.data)
  } catch (error) {
    session.setAnonymous()
    throw error
  }
}

export async function resendVerificationCode(email: string): Promise<void> {
  const response = await resendCodeApiV1AuthResendCodePost({ email })
  if (response.status !== 202) {
    throw new ApiError({
      status: response.status,
      code: 'resend_failed',
      message: 'Не удалось отправить новый код.',
    })
  }
}

export async function logoutCandidate(): Promise<void> {
  await invalidateSessionForLogout()
  await logoutApiV1AuthLogoutPost()
}

export const authTestApi = {
  reset(): void {
    restoreOperation = null
  },
}
