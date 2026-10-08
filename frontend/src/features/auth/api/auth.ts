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
import { ApiError } from '@/shared/api/transport/api-error'
import { session } from '@/shared/session/session'

type RegisterCandidateInput = {
  email: string
  password: string
  fullName?: string
}

async function establishCandidateSession(tokenData: TokenResponse): Promise<void> {
  session.clear()
  session.setTokens({
    accessToken: tokenData.access_token,
    refreshToken: tokenData.refresh_token,
    expiresIn: tokenData.expires_in,
    refreshExpiresIn: tokenData.refresh_expires_in,
  })

  try {
    const { data: user } = await meApiV1UsersMeGet()
    if (user.role !== 'candidate') {
      throw new ApiError({
        status: 403,
        code: 'candidate_access_required',
        message: 'Этот кабинет доступен только пользователям с ролью кандидата.',
      })
    }

    session.setUser({
      id: user.id,
      email: user.email,
      role: user.role,
      fullName: user.full_name,
      isEmailVerified: user.is_email_verified,
    })
  } catch (error) {
    session.clear()
    throw error
  }
}

export async function loginCandidate(credentials: LoginRequest): Promise<void> {
  session.clear()
  const tokenResponse = await loginApiV1AuthLoginPost(credentials)
  if (tokenResponse.status !== 200) {
    throw new ApiError({ status: tokenResponse.status, code: 'login_failed', message: 'Не удалось войти.' })
  }
  await establishCandidateSession(tokenResponse.data)
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
  const response = await verifyEmailApiV1AuthVerifyEmailPost({ email, code })
  if (response.status !== 200) {
    throw new ApiError({
      status: response.status,
      code: 'verification_failed',
      message: 'Не удалось подтвердить почту.',
    })
  }
  await establishCandidateSession(response.data)
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
  const refreshToken = session.getSnapshot().tokens?.refreshToken
  session.clear()

  if (refreshToken) {
    await logoutApiV1AuthLogoutPost({ refresh_token: refreshToken })
  }
}
