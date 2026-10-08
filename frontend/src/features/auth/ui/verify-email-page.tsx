import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Controller, useForm } from 'react-hook-form'

import { resendVerificationCode, verifyCandidateEmail } from '@/features/auth/api/auth'
import { useCountdown } from '@/features/auth/model/use-countdown'
import {
  verificationFlow,
  useVerificationFlow,
} from '@/features/auth/model/verification-flow'
import {
  verifyEmailSchema,
  type VerifyEmailValues,
} from '@/features/auth/model/verify-email-schema'
import { AuthPageLayout } from '@/features/auth/ui/auth-page-layout'
import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/shared/ui/input-otp'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'

function verificationErrorMessage(error: unknown): string {
  if (!isApiError(error)) return 'Не удалось подтвердить почту. Повторите попытку.'
  if (error.code === 'invalid_code') return 'Код не подходит. Проверьте цифры и попробуйте снова.'
  if (error.code === 'code_expired') return 'Срок действия кода истёк. Отправьте новый код.'
  if (error.code === 'too_many_attempts') return 'Слишком много неверных попыток. Отправьте новый код.'
  if (error.code === 'already_verified') return 'Эта почта уже подтверждена. Войдите в аккаунт.'
  if (error.status === 429) {
    return error.retryAfterSeconds === null
      ? 'Слишком много попыток. Попробуйте позже.'
      : `Слишком много попыток. Повторите через ${error.retryAfterSeconds} сек.`
  }
  return error.message
}

function resendErrorMessage(error: unknown): string {
  if (!isApiError(error)) return 'Не удалось отправить код. Проверьте соединение.'
  if (error.code === 'resend_cooldown' || error.status === 429) {
    return error.retryAfterSeconds === null
      ? 'Новый код можно будет отправить позже.'
      : `Новый код можно отправить через ${error.retryAfterSeconds} сек.`
  }
  return error.message
}

export function VerifyEmailPage() {
  const navigate = useNavigate()
  const flow = useVerificationFlow()
  const resendSeconds = useCountdown(flow.resendAvailableAt)
  const codeExpirySeconds = useCountdown(flow.codeExpiresAt ?? 0)
  const form = useForm<VerifyEmailValues>({
    resolver: zodResolver(verifyEmailSchema),
    defaultValues: { email: flow.email, code: '' },
  })
  const verification = useMutation({
    mutationFn: (values: VerifyEmailValues) => verifyCandidateEmail(values.email, values.code),
    onSuccess: () => {
      verificationFlow.clear()
      void navigate({ to: '/profile', replace: true })
    },
  })
  const resend = useMutation({
    mutationFn: resendVerificationCode,
    onSuccess: () => verificationFlow.markResent(),
    onError: (error) => {
      if (isApiError(error) && error.status === 429) {
        verificationFlow.markResent(error.retryAfterSeconds ?? flow.resendCooldownSeconds)
      }
    },
  })

  async function handleResend(): Promise<void> {
    const emailIsValid = await form.trigger('email')
    if (!emailIsValid || resendSeconds > 0 || resend.isPending) return
    const email = form.getValues('email')
    verificationFlow.setEmail(email)
    resend.mutate(email)
  }

  function changeEmail(): void {
    verificationFlow.clear()
    void navigate({ to: '/register' })
  }

  const expiryMinutes = flow.codeExpiresAt
    ? Math.max(1, Math.ceil(codeExpirySeconds / 60))
    : null

  return (
    <AuthPageLayout>
      <Card>
        <CardHeader>
          <CardTitle>Подтвердите почту</CardTitle>
          <CardDescription>
            {flow.email ? (
              <>
                Код отправлен на <span className="font-medium text-foreground">{flow.email}</span>.
              </>
            ) : (
              'Укажите почту и введите код из письма.'
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            noValidate
            onSubmit={(event) => {
              void form.handleSubmit((values) => {
                verificationFlow.setEmail(values.email)
                verification.mutate(values)
              })(event)
            }}
          >
            {verification.isError ? (
              <Alert variant="destructive">
                <AlertCircle className="size-4" aria-hidden="true" />
                <AlertTitle>Не удалось подтвердить почту</AlertTitle>
                <AlertDescription>{verificationErrorMessage(verification.error)}</AlertDescription>
              </Alert>
            ) : null}

            {resend.isSuccess ? (
              <Alert variant="success">
                <CheckCircle2 className="size-4" aria-hidden="true" />
                <AlertTitle>Новый код отправлен</AlertTitle>
                <AlertDescription>Проверьте почту и введите код из последнего письма.</AlertDescription>
              </Alert>
            ) : null}

            {resend.isError ? (
              <Alert variant="destructive">
                <AlertCircle className="size-4" aria-hidden="true" />
                <AlertTitle>Код не отправлен</AlertTitle>
                <AlertDescription>{resendErrorMessage(resend.error)}</AlertDescription>
              </Alert>
            ) : null}

            {flow.email ? (
              <input type="hidden" {...form.register('email')} />
            ) : (
              <div className="space-y-2">
                <Label htmlFor="verification-email">Почта</Label>
                <Input
                  id="verification-email"
                  type="email"
                  autoComplete="email"
                  placeholder="candidate@example.ru"
                  aria-invalid={Boolean(form.formState.errors.email)}
                  aria-describedby={form.formState.errors.email ? 'verification-email-error' : undefined}
                  {...form.register('email')}
                />
                {form.formState.errors.email ? (
                  <p id="verification-email-error" className="text-sm text-destructive">
                    {form.formState.errors.email.message}
                  </p>
                ) : null}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="verification-code">Код из письма</Label>
              <Controller
                control={form.control}
                name="code"
                render={({ field }) => (
                  <InputOTP
                    id="verification-code"
                    maxLength={6}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]*"
                    aria-invalid={Boolean(form.formState.errors.code)}
                    aria-describedby={form.formState.errors.code ? 'verification-code-error' : 'verification-code-help'}
                    value={field.value}
                    onBlur={field.onBlur}
                    onChange={(value) => field.onChange(value.replace(/\D/g, '').slice(0, 6))}
                  >
                    <InputOTPGroup>
                      {Array.from({ length: 6 }, (_, index) => (
                        <InputOTPSlot key={index} index={index} />
                      ))}
                    </InputOTPGroup>
                  </InputOTP>
                )}
              />
              <p id="verification-code-help" className="text-xs leading-5 text-muted-foreground">
                {expiryMinutes ? `Код действует ещё около ${expiryMinutes} мин.` : 'Введите шесть цифр из письма.'}
              </p>
              {form.formState.errors.code ? (
                <p id="verification-code-error" className="text-sm text-destructive">
                  {form.formState.errors.code.message}
                </p>
              ) : null}
            </div>

            <Button className="w-full" type="submit" disabled={verification.isPending}>
              {verification.isPending ? <Spinner label="Проверяем код…" /> : 'Подтвердить'}
            </Button>
            <Button
              className="w-full"
              type="button"
              variant="outline"
              aria-label="Отправить код повторно"
              disabled={resendSeconds > 0 || resend.isPending}
              onClick={() => void handleResend()}
            >
              {resend.isPending ? (
                <Spinner label="Отправляем…" />
              ) : (
                <>
                  <span>Отправить код повторно</span>
                  {resendSeconds > 0 ? <span aria-hidden="true">· {resendSeconds} с</span> : null}
                </>
              )}
            </Button>
            <Button className="w-full" type="button" variant="ghost" onClick={changeEmail}>
              Изменить почту
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthPageLayout>
  )
}
