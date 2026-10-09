import { zodResolver } from '@hookform/resolvers/zod'
import { useCallback, type ReactNode } from 'react'
import { Controller, useForm } from 'react-hook-form'

import { useRegisterProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import {
  personalSchema,
  type PersonalValues,
} from '@/features/candidate-profile/model/profile-schemas'
import { useProfileSectionSave } from '@/features/candidate-profile/model/use-profile-section-save'
import {
  SaveState,
  SectionActions,
  SectionFormCard,
} from '@/features/candidate-profile/ui/section-form-layout'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Checkbox } from '@/shared/ui/checkbox'

function valuesFromProfile(profile: ProfileResponse): PersonalValues {
  return {
    lastName: profile.last_name ?? '',
    firstName: profile.first_name ?? '',
    middleName: profile.middle_name ?? '',
    birthDate: profile.birth_date ?? '',
    city: profile.city ?? '',
    relocationReady: profile.relocation_ready,
  }
}

function dateYearsAgo(years: number): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() - years)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function PersonalForm({
  profile,
  onContinue,
  standalone = false,
}: {
  profile: ProfileResponse
  onContinue: () => void
  standalone?: boolean
}) {
  const form = useForm<PersonalValues>({
    resolver: zodResolver(personalSchema),
    defaultValues: valuesFromProfile(profile),
  })
  const applyProfile = useCallback(
    (next: ProfileResponse) => form.reset(valuesFromProfile(next)),
    [form],
  )
  const save = useProfileSectionSave({
    profile,
    isDirty: form.formState.isDirty,
    applyProfile,
    onError: (error) => {
      if (!isApiError(error)) return
      const fields = {
        last_name: 'lastName',
        first_name: 'firstName',
        middle_name: 'middleName',
        birth_date: 'birthDate',
        city: 'city',
        relocation_ready: 'relocationReady',
      } as const
      error.fieldIssues.forEach((issue) => {
        const apiField = issue.field.split('.').at(-1)
        const field = apiField ? fields[apiField as keyof typeof fields] : undefined
        if (field) form.setError(field, { type: 'server', message: issue.message })
      })
    },
  })

  async function saveForm(): Promise<boolean> {
    if (!form.formState.isDirty) return true
    let succeeded = false
    await form.handleSubmit(async (values) => {
      succeeded = await save.save({
        last_name: values.lastName || null,
        first_name: values.firstName || null,
        middle_name: values.middleName || null,
        birth_date: values.birthDate || null,
        city: values.city || null,
        relocation_ready: values.relocationReady,
      })
    })()
    return succeeded
  }

  function discard(): void {
    form.reset(valuesFromProfile(profile))
  }

  useRegisterProfileDraft('personal', form.formState.isDirty, saveForm, discard)

  return (
    <SectionFormCard
      title="Личные данные"
      description="Основная информация профиля. Фамилия и имя нужны для публикации."
      standalone={standalone}
    >
      <form className="space-y-6" noValidate onSubmit={(event) => event.preventDefault()}>
        <SaveState
          confirmation={save.confirmation}
          error={save.error}
          dirty={form.formState.isDirty}
          retrying={save.isRetryingConfirmation}
          onRetry={() => void save.retryConfirmation().then((ok) => { if (ok && standalone) onContinue() })}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Фамилия" id="last-name" error={form.formState.errors.lastName?.message}>
            <Input id="last-name" autoComplete="family-name" {...form.register('lastName')} />
          </Field>
          <Field label="Имя" id="first-name" error={form.formState.errors.firstName?.message}>
            <Input id="first-name" autoComplete="given-name" {...form.register('firstName')} />
          </Field>
          <Field label="Отчество" id="middle-name" error={form.formState.errors.middleName?.message}>
            <Input id="middle-name" autoComplete="additional-name" {...form.register('middleName')} />
          </Field>
          <Field label="Дата рождения" id="birth-date" error={form.formState.errors.birthDate?.message}>
            <Input id="birth-date" type="date" autoComplete="bday" min={dateYearsAgo(100)} max={dateYearsAgo(14)} {...form.register('birthDate')} />
          </Field>
          <Field label="Город" id="city" error={form.formState.errors.city?.message} className="sm:col-span-2">
            <Input id="city" autoComplete="address-level2" {...form.register('city')} />
          </Field>
        </div>
        <Controller
          control={form.control}
          name="relocationReady"
          render={({ field }) => (
            <label className="flex min-h-12 cursor-pointer items-start gap-3 py-2 text-sm transition-colors hover:text-primary">
              <Checkbox className="mt-0.5" checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />
              <span>
                <span className="block font-medium">Готов к переезду</span>
                <span className="mt-1 block text-muted-foreground">Работодатели увидят эту готовность в профиле.</span>
              </span>
            </label>
          )}
        />
        <SectionActions
          dirty={form.formState.isDirty}
          pending={save.isPending}
          hasNext={!standalone}
          onSave={() => void saveForm().then((ok) => { if (ok && standalone) onContinue() })}
          onSaveAndContinue={() => void saveForm().then((ok) => { if (ok) onContinue() })}
        />
      </form>
    </SectionFormCard>
  )
}

function Field({
  label,
  id,
  error,
  className,
  children,
}: {
  label: string
  id: string
  error?: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={`space-y-2 ${className ?? ''}`}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
