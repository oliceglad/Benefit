import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, RotateCcw, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'

import {
  candidateProfileQueryKey,
  getCandidateProfile,
  updateCandidateProfile,
} from '@/features/candidate-profile/api/profile'
import {
  contactSchema,
  type ContactValues,
} from '@/features/candidate-profile/model/contact-schema'
import { formatPhone, normalizePhone, normalizeTelegram } from '@/features/candidate-profile/model/form-values'
import { PhoneInput } from '@/features/candidate-profile/ui/phone-input'
import { useRegisterProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import { SectionActions } from '@/features/candidate-profile/ui/section-form-layout'
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
    phone: formatPhone(profile.phone ?? ''),
    contactEmail: profile.contact_email ?? '',
    telegram: profile.telegram ?? '',
  }
}

export function ContactForm({ onContinue = () => undefined, standalone = false }: { onContinue?: () => void; standalone?: boolean }) {
  const queryClient = useQueryClient()
  const [confirmation, setConfirmation] = useState<'confirmed' | 'unconfirmed' | null>(null)
  const confirmationRef = useRef<'confirmed' | 'unconfirmed' | null>(null)
  const [retryingConfirmation, setRetryingConfirmation] = useState(false)

  function updateConfirmation(value: 'confirmed' | 'unconfirmed' | null): void {
    confirmationRef.current = value
    setConfirmation(value)
  }
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
        phone: values.phone ? normalizePhone(values.phone) : null,
        contact_email: values.contactEmail || null,
        telegram: values.telegram ? normalizeTelegram(values.telegram) : null,
      }),
    onMutate: () => updateConfirmation(null),
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
        updateConfirmation('confirmed')
      } catch {
        updateConfirmation('unconfirmed')
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

  async function saveForm(): Promise<boolean> {
    if (!form.formState.isDirty) return true
    let succeeded = false
    await form.handleSubmit(async (values) => {
      try {
        await save.mutateAsync(values)
        succeeded = confirmationRef.current === 'confirmed'
      } catch {
        succeeded = false
      }
    })()
    return succeeded
  }

  async function retryConfirmation(): Promise<void> {
    setRetryingConfirmation(true)
    try {
      const confirmed = await queryClient.fetchQuery({ queryKey: candidateProfileQueryKey, queryFn: ({ signal }) => getCandidateProfile(signal), staleTime: 0 })
      form.reset(valuesFromProfile(confirmed))
      updateConfirmation('confirmed')
      if (standalone) onContinue()
    } catch {
      updateConfirmation('unconfirmed')
    } finally {
      setRetryingConfirmation(false)
    }
  }

  function discard(): void {
    if (profile.data) form.reset(valuesFromProfile(profile.data))
  }

  useRegisterProfileDraft('contacts', form.formState.isDirty, saveForm, discard)

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
    <Card className={standalone ? 'border-0 shadow-none' : undefined}>
      <CardHeader className={standalone ? 'sr-only' : undefined}>
        <CardTitle>Контакты</CardTitle>
        <CardDescription>
          Контакты увидит только работодатель, чьё приглашение вы приняли или на чью вакансию откликнулись.
        </CardDescription>
      </CardHeader>
      <CardContent className={standalone ? 'p-0' : undefined}>
        <form
          className="space-y-6"
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            void saveForm().then((ok) => { if (ok && standalone) onContinue() })
          }}
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
              <AlertDescription className="space-y-3">
                <p>Не удалось получить актуальные данные. Повторите получение, прежде чем покинуть раздел.</p>
                <Button type="button" size="sm" variant="outline" disabled={retryingConfirmation} onClick={() => void retryConfirmation()}>{retryingConfirmation ? <Spinner label="Получаем данные…" /> : 'Повторить получение'}</Button>
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
              <Controller
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <PhoneInput
                    id="phone"
                    ref={field.ref}
                    name={field.name}
                    value={field.value}
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    placeholder="+7 (999) 123-45-67"
                    aria-invalid={Boolean(form.formState.errors.phone)}
                    aria-describedby={form.formState.errors.phone ? 'phone-error' : 'phone-help'}
                    onValueChange={field.onChange}
                    onBlur={field.onBlur}
                  />
                )}
              />
              <p id="phone-help" className="text-xs leading-5 text-muted-foreground">Можно ввести российский номер с +7 или 8 либо международный номер.</p>
              {form.formState.errors.phone ? (
                <p id="phone-error" className="text-sm text-destructive">
                  {form.formState.errors.phone.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="telegram">Telegram</Label>
              <Controller
                control={form.control}
                name="telegram"
                render={({ field }) => (
                  <Input
                    id="telegram"
                    ref={field.ref}
                    name={field.name}
                    value={field.value}
                    autoComplete="off"
                    placeholder="@username или t.me/username"
                    aria-invalid={Boolean(form.formState.errors.telegram)}
                    aria-describedby={form.formState.errors.telegram ? 'telegram-error' : undefined}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                  />
                )}
              />
              {form.formState.errors.telegram ? (
                <p id="telegram-error" className="text-sm text-destructive">
                  {form.formState.errors.telegram.message}
                </p>
              ) : null}
            </div>
          </div>

          <SectionActions
            dirty={form.formState.isDirty}
            pending={save.isPending}
            hasNext={!standalone}
            onSave={() => void saveForm().then((ok) => { if (ok && standalone) onContinue() })}
            onSaveAndContinue={() => void saveForm().then((ok) => { if (ok) onContinue() })}
          />
        </form>
      </CardContent>
    </Card>
  )
}
