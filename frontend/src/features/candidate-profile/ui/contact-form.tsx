import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, RotateCcw, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'

import {
  candidateProfileQueryKey,
  getCandidateProfile,
  updateCandidateProfile,
} from '@/features/candidate-profile/api/profile'
import {
  contactSchema,
  type ContactValues,
} from '@/features/candidate-profile/model/contact-schema'
import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'

const emptyContacts: ContactValues = { phone: '', contactEmail: '', telegram: '' }

function valuesFromProfile(profile: {
  phone: string | null
  contact_email: string | null
  telegram: string | null
}): ContactValues {
  return {
    phone: profile.phone ?? '',
    contactEmail: profile.contact_email ?? '',
    telegram: profile.telegram ?? '',
  }
}

export function ContactForm() {
  const queryClient = useQueryClient()
  const [confirmation, setConfirmation] = useState<'confirmed' | 'unconfirmed' | null>(null)
  const profile = useQuery({
    queryKey: candidateProfileQueryKey,
    queryFn: ({ signal }) => getCandidateProfile(signal),
  })
  const form = useForm<ContactValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: emptyContacts,
  })
  const save = useMutation({
    mutationFn: (values: ContactValues) =>
      updateCandidateProfile({
        phone: values.phone || null,
        contact_email: values.contactEmail || null,
        telegram: values.telegram || null,
      }),
    onMutate: () => setConfirmation(null),
    onSuccess: async (updated) => {
      form.reset(valuesFromProfile(updated))
      queryClient.setQueryData(candidateProfileQueryKey, updated)
      try {
        const confirmed = await queryClient.fetchQuery({
          queryKey: candidateProfileQueryKey,
          queryFn: ({ signal }) => getCandidateProfile(signal),
          staleTime: 0,
        })
        form.reset(valuesFromProfile(confirmed))
        setConfirmation('confirmed')
      } catch {
        setConfirmation('unconfirmed')
      }
    },
    onError: (error) => {
      if (!isApiError(error)) return
      const fields = {
        phone: 'phone',
        contact_email: 'contactEmail',
        telegram: 'telegram',
      } as const
      error.fieldIssues.forEach((issue) => {
        const apiField = issue.field.split('.').at(-1)
        const formField = apiField ? fields[apiField as keyof typeof fields] : undefined
        if (formField) form.setError(formField, { type: 'server', message: issue.message })
      })
    },
  })

  useEffect(() => {
    if (profile.data && !form.formState.isDirty && !save.isPending) {
      form.reset(valuesFromProfile(profile.data))
    }
  }, [form, profile.data, save.isPending])

  if (profile.isPending) {
    return (
      <Card className="min-h-80">
        <CardContent className="grid min-h-80 place-items-center">
          <Spinner label="Загружаем профиль…" />
        </CardContent>
      </Card>
    )
  }

  if (profile.isError && !profile.data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        <AlertTitle>Профиль не загрузился</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{isApiError(profile.error) ? profile.error.message : 'Повторите попытку.'}</p>
          <Button variant="outline" size="sm" onClick={() => void profile.refetch()}>
            <RotateCcw aria-hidden="true" />
            Повторить
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Контакты</CardTitle>
        <CardDescription>
          Контакты увидит только работодатель, чьё приглашение вы приняли или на чью вакансию откликнулись.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-6"
          noValidate
          onSubmit={(event) => void form.handleSubmit((values) => save.mutate(values))(event)}
        >
          {save.isSuccess && confirmation === 'confirmed' && !form.formState.isDirty ? (
            <Alert variant="success">
              <CheckCircle2 className="size-4" aria-hidden="true" />
              <AlertTitle>Контакты сохранены</AlertTitle>
              <AlertDescription>Изменения применены.</AlertDescription>
            </Alert>
          ) : null}

          {save.isSuccess && confirmation === 'unconfirmed' ? (
            <Alert variant="warning">
              <TriangleAlert className="size-4" aria-hidden="true" />
              <AlertTitle>Контакты сохранены</AlertTitle>
              <AlertDescription>
                Не удалось получить актуальные данные. Обновите профиль позже.
              </AlertDescription>
            </Alert>
          ) : null}

          {save.isError ? (
            <Alert variant="destructive">
              <AlertCircle className="size-4" aria-hidden="true" />
              <AlertTitle>Не удалось сохранить</AlertTitle>
              <AlertDescription>
                {isApiError(save.error) ? save.error.message : 'Проверьте данные и повторите попытку.'}
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="contact-email">Контактная почта</Label>
              <Input
                id="contact-email"
                type="email"
                autoComplete="email"
                placeholder="name@example.ru"
                aria-invalid={Boolean(form.formState.errors.contactEmail)}
                aria-describedby={form.formState.errors.contactEmail ? 'contact-email-error' : 'contact-email-help'}
                {...form.register('contactEmail')}
              />
              <p id="contact-email-help" className="text-xs leading-5 text-muted-foreground">
                Может отличаться от почты для входа.
              </p>
              {form.formState.errors.contactEmail ? (
                <p id="contact-email-error" className="text-sm text-destructive">
                  {form.formState.errors.contactEmail.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Телефон</Label>
              <Input
                id="phone"
                type="tel"
                autoComplete="tel"
                placeholder="+7 900 000-00-00"
                aria-invalid={Boolean(form.formState.errors.phone)}
                aria-describedby={form.formState.errors.phone ? 'phone-error' : undefined}
                {...form.register('phone')}
              />
              {form.formState.errors.phone ? (
                <p id="phone-error" className="text-sm text-destructive">
                  {form.formState.errors.phone.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="telegram">Telegram</Label>
              <Input
                id="telegram"
                autoComplete="off"
                placeholder="@username"
                aria-invalid={Boolean(form.formState.errors.telegram)}
                aria-describedby={form.formState.errors.telegram ? 'telegram-error' : undefined}
                {...form.register('telegram')}
              />
              {form.formState.errors.telegram ? (
                <p id="telegram-error" className="text-sm text-destructive">
                  {form.formState.errors.telegram.message}
                </p>
              ) : null}
            </div>
          </div>

          <div className="flex flex-col-reverse gap-3 border-t pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-muted-foreground" aria-live="polite">
              {form.formState.isDirty ? 'Есть несохранённые изменения' : 'Все изменения сохранены'}
            </p>
            <Button type="submit" disabled={save.isPending || !form.formState.isDirty}>
              {save.isPending ? <Spinner label="Сохраняем…" /> : 'Сохранить контакты'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
