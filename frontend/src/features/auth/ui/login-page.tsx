import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { AlertCircle } from 'lucide-react'
import { useForm } from 'react-hook-form'

import { loginAccount } from '@/features/auth/api/auth'
import { loginSchema, type LoginValues } from '@/features/auth/model/login-schema'
import { verificationFlow } from '@/features/auth/model/verification-flow'
import { AuthPageLayout } from '@/features/auth/ui/auth-page-layout'
import { PasswordInput } from '@/features/auth/ui/password-input'
import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'

function loginErrorMessage(error: unknown): string {
  if (!isApiError(error)) return 'Не удалось войти. Повторите попытку.'
  if (error.status === 401) return 'Неверная почта или пароль.'
  if (error.status === 403) return error.message
  if (error.status === 429) {
    return error.retryAfterSeconds === null
      ? 'Слишком много попыток. Попробуйте позже.'
      : `Слишком много попыток. Повторите через ${error.retryAfterSeconds} сек.`
  }
  return error.message
}

export function LoginPage() {
  const navigate = useNavigate()
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })
  const login = useMutation({
    mutationFn: loginAccount,
    onSuccess: () => navigate({ to: '/', replace: true }),
  })
  const emailNotVerified = isApiError(login.error) && login.error.code === 'email_not_verified'

  function continueVerification(): void {
    verificationFlow.setEmail(form.getValues('email').trim().toLowerCase())
    void navigate({ to: '/verify-email' })
  }

  return (
    <AuthPageLayout>
      <Card>
        <CardHeader>
          <CardTitle>Вход в кабинет</CardTitle>
          <CardDescription>
            Используйте почту и пароль кандидата или работодателя.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            noValidate
            onSubmit={(event) => void form.handleSubmit((values) => login.mutate(values))(event)}
          >
            {login.isError ? (
              <Alert variant="destructive">
                <AlertCircle className="size-4" aria-hidden="true" />
                <AlertTitle>Не удалось войти</AlertTitle>
                <AlertDescription className="space-y-3">
                  <p>{loginErrorMessage(login.error)}</p>
                  {emailNotVerified ? (
                    <Button type="button" size="sm" variant="outline" onClick={continueVerification}>
                      Подтвердить почту
                    </Button>
                  ) : null}
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="email">Почта</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="candidate@example.ru"
                aria-invalid={Boolean(form.formState.errors.email)}
                aria-describedby={form.formState.errors.email ? 'email-error' : undefined}
                {...form.register('email')}
              />
              {form.formState.errors.email ? (
                <p id="email-error" className="text-sm text-destructive">
                  {form.formState.errors.email.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <PasswordInput
                id="password"
                autoComplete="current-password"
                aria-invalid={Boolean(form.formState.errors.password)}
                aria-describedby={form.formState.errors.password ? 'password-error' : undefined}
                {...form.register('password')}
              />
              {form.formState.errors.password ? (
                <p id="password-error" className="text-sm text-destructive">
                  {form.formState.errors.password.message}
                </p>
              ) : null}
            </div>

            <Button className="w-full" type="submit" disabled={login.isPending}>
              {login.isPending ? <Spinner label="Входим…" /> : 'Войти'}
            </Button>
            <Button className="w-full" type="button" variant="outline" asChild>
              <Link to="/register">Создать аккаунт</Link>
            </Button>
          </form>
        </CardContent>
      </Card>

    </AuthPageLayout>
  )
}
