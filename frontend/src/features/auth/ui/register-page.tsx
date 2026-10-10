import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { AlertCircle } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { registerAccount } from '@/features/auth/api/auth'
import { registerSchema, type RegisterValues } from '@/features/auth/model/register-schema'
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

function registrationErrorMessage(error: unknown): string {
  if (!isApiError(error)) return 'Не удалось создать аккаунт. Повторите попытку.'
  if (error.code === 'email_taken') return 'Аккаунт с этой почтой уже существует.'
  if (error.code === 'email_domain_not_allowed') return 'Регистрация доступна для почты в российских доменах.'
  if (error.code === 'mail_unavailable') return 'Аккаунт создан, но письмо не отправлено. Попробуйте отправить код позже.'
  if (error.status === 429) {
    return error.retryAfterSeconds === null
      ? 'Слишком много попыток. Попробуйте позже.'
      : `Слишком много попыток. Повторите через ${error.retryAfterSeconds} сек.`
  }
  return error.message
}

export function RegisterPage() {
  const [role, setRole] = useState<'candidate' | 'employer'>('candidate')
  const navigate = useNavigate()
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { fullName: '', email: '', password: '' },
  })
  const registration = useMutation({
    mutationFn: (values: RegisterValues) => registerAccount({ ...values, role }),
    onSuccess: (response) => {
      verificationFlow.start(
        response.email,
        response.code_expires_in,
        response.resend_available_in,
      )
      void navigate({ to: '/verify-email' })
    },
    onError: (error) => {
      if (!isApiError(error)) return
      error.fieldIssues.forEach((issue) => {
        const field = issue.field.split('.').at(-1)
        if (field === 'email' || field === 'password' || field === 'full_name') {
          form.setError(field === 'full_name' ? 'fullName' : field, {
            type: 'server',
            message: issue.message,
          })
        }
      })
      if (error.code === 'email_domain_not_allowed' || error.code === 'email_taken') {
        form.setError('email', { type: 'server', message: registrationErrorMessage(error) })
      }
    },
  })

  function continueAfterMailFailure(): void {
    const email = form.getValues('email')
    verificationFlow.setEmail(email)
    void navigate({ to: '/verify-email' })
  }

  return (
    <AuthPageLayout>
      <Card>
        <CardHeader>
          <CardTitle>Создание аккаунта</CardTitle>
          <CardDescription>Выберите, как вы будете использовать Benefit.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            noValidate
            onSubmit={(event) =>
              void form.handleSubmit((values) => registration.mutate(values))(event)
            }
          >
            <fieldset disabled={registration.isPending} className="space-y-2">
              <legend className="mb-2 text-sm font-medium">Тип аккаунта</legend>
              <div className="grid grid-cols-2 gap-2">
                <Button type="button" variant={role === 'candidate' ? 'default' : 'outline'} aria-pressed={role === 'candidate'} onClick={() => setRole('candidate')}>Кандидат</Button>
                <Button type="button" variant={role === 'employer' ? 'default' : 'outline'} aria-pressed={role === 'employer'} onClick={() => setRole('employer')}>Работодатель</Button>
              </div>
            </fieldset>
            {registration.isError ? (
              <Alert variant="destructive">
                <AlertCircle className="size-4" aria-hidden="true" />
                <AlertTitle>Не удалось зарегистрироваться</AlertTitle>
                <AlertDescription>{registrationErrorMessage(registration.error)}</AlertDescription>
                {isApiError(registration.error) && registration.error.code === 'mail_unavailable' ? (
                  <Button type="button" variant="outline" size="sm" onClick={continueAfterMailFailure}>
                    Перейти к подтверждению
                  </Button>
                ) : null}
              </Alert>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="full-name">Имя и фамилия</Label>
              <Input
                id="full-name"
                autoComplete="name"
                placeholder="Анна Иванова"
                aria-invalid={Boolean(form.formState.errors.fullName)}
                aria-describedby={form.formState.errors.fullName ? 'full-name-error' : 'full-name-help'}
                {...form.register('fullName')}
              />
              <p id="full-name-help" className="text-xs leading-5 text-muted-foreground">
                Необязательно.
              </p>
              {form.formState.errors.fullName ? (
                <p id="full-name-error" className="text-sm text-destructive">
                  {form.formState.errors.fullName.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="register-email">Почта</Label>
              <Input
                id="register-email"
                type="email"
                autoComplete="email"
                placeholder="candidate@example.ru"
                aria-invalid={Boolean(form.formState.errors.email)}
                aria-describedby={form.formState.errors.email ? 'register-email-error' : 'register-email-help'}
                {...form.register('email')}
              />
              <p id="register-email-help" className="text-xs leading-5 text-muted-foreground">
                Используйте адрес в домене .ru, .su или .рф.
              </p>
              {form.formState.errors.email ? (
                <p id="register-email-error" className="text-sm text-destructive">
                  {form.formState.errors.email.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="register-password">Пароль</Label>
              <PasswordInput
                id="register-password"
                autoComplete="new-password"
                aria-invalid={Boolean(form.formState.errors.password)}
                aria-describedby={form.formState.errors.password ? 'register-password-error' : 'register-password-help'}
                {...form.register('password')}
              />
              <p id="register-password-help" className="text-xs leading-5 text-muted-foreground">
                От 8 до 128 символов, минимум одна буква и одна цифра.
              </p>
              {form.formState.errors.password ? (
                <p id="register-password-error" className="text-sm text-destructive">
                  {form.formState.errors.password.message}
                </p>
              ) : null}
            </div>

            <Button className="w-full" type="submit" disabled={registration.isPending}>
              {registration.isPending ? <Spinner label="Создаём аккаунт…" /> : 'Создать аккаунт'}
            </Button>
            <Button className="w-full" type="button" variant="outline" asChild>
              <Link to="/login">Уже есть аккаунт</Link>
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthPageLayout>
  )
}
