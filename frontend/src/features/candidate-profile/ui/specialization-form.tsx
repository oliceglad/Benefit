import { zodResolver } from '@hookform/resolvers/zod'
import { BadgeCheck } from 'lucide-react'
import { useCallback } from 'react'
import { Controller, useForm } from 'react-hook-form'

import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import { useRegisterProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import {
  roleSchema,
  specializationSchema,
  type SpecializationValues,
} from '@/features/candidate-profile/model/profile-schemas'
import { useProfileSectionSave } from '@/features/candidate-profile/model/use-profile-section-save'
import {
  SaveState,
  SectionActions,
  SectionFormCard,
} from '@/features/candidate-profile/ui/section-form-layout'
import { SearchableMultiSelect } from '@/features/candidate-profile/ui/searchable-multi-select'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { SelectField } from '@/shared/ui/select-field'
import { Textarea } from '@/shared/ui/textarea'

function valuesFromProfile(profile: ProfileResponse): SpecializationValues {
  return {
    headline: profile.headline ?? '',
    about: profile.about ?? '',
    grade: profile.grade ?? '',
    roles: profile.roles,
  }
}

export function SpecializationForm({
  profile,
  dictionaries,
  onContinue,
  standalone = false,
}: {
  profile: ProfileResponse
  dictionaries: ProfileDictionaries
  onContinue: () => void
  standalone?: boolean
}) {
  const form = useForm<SpecializationValues>({
    resolver: zodResolver(specializationSchema),
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
      const fields = { headline: 'headline', about: 'about', grade: 'grade', roles: 'roles' } as const
      error.fieldIssues.forEach((issue) => {
        const apiField = issue.field.split('.').at(-1)
        const field = apiField ? fields[apiField as keyof typeof fields] : undefined
        if (field) form.setError(field, { type: 'server', message: issue.message })
      })
    },
  })
  const roleOptions = dictionaries.roles.flatMap((option) => {
    const parsed = roleSchema.safeParse(option.id)
    return parsed.success ? [{ ...option, id: parsed.data }] : []
  })

  async function saveForm(): Promise<boolean> {
    if (!form.formState.isDirty) return true
    let succeeded = false
    await form.handleSubmit(async (values) => {
      succeeded = await save.save({
        headline: values.headline || null,
        about: values.about || null,
        grade: values.grade || null,
        roles: values.roles,
      })
    })()
    return succeeded
  }

  useRegisterProfileDraft(
    'specialization',
    form.formState.isDirty,
    saveForm,
    () => form.reset(valuesFromProfile(profile)),
  )

  const gradeTitle = dictionaries.grades.find((option) => option.id === profile.verified_grade)?.title
  const roleTitle = dictionaries.roles.find((option) => option.id === profile.verified_specialization)?.title

  return (
    <SectionFormCard
      title="Специализация и грейд"
      description="Расскажите, какую работу ищете. Подтверждённый грейд появится после проверки навыков."
      standalone={standalone}
    >
      <form className="space-y-6" noValidate onSubmit={(event) => event.preventDefault()}>
        <SaveState confirmation={save.confirmation} error={save.error} dirty={form.formState.isDirty} retrying={save.isRetryingConfirmation} onRetry={() => void save.retryConfirmation().then((ok) => { if (ok && standalone) onContinue() })} />

        {profile.verified_grade || profile.verified_specialization ? (
          <Alert variant="success">
            <BadgeCheck className="size-4" aria-hidden="true" />
            <AlertTitle>Подтверждённая квалификация</AlertTitle>
            <AlertDescription>
              {[roleTitle, gradeTitle].filter(Boolean).join(' · ')}
              {profile.grade_verified_at
                ? ` · ${new Intl.DateTimeFormat('ru-RU').format(new Date(profile.grade_verified_at))}`
                : ''}
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="headline">Желаемая должность</Label>
          <Input id="headline" placeholder="Frontend-разработчик" {...form.register('headline')} />
          {form.formState.errors.headline ? <p className="text-sm text-destructive">{form.formState.errors.headline.message}</p> : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="grade">Заявленный грейд</Label>
          <Controller
            control={form.control}
            name="grade"
            render={({ field }) => (
              <SelectField
                id="grade"
                value={field.value}
                onValueChange={field.onChange}
                options={[{ value: '', label: 'Не выбран' }, ...dictionaries.grades.map((option) => ({ value: option.id, label: option.title }))]}
              />
            )}
          />
          {form.formState.errors.grade ? <p className="text-sm text-destructive">{form.formState.errors.grade.message}</p> : null}
        </div>

        <Controller
          control={form.control}
          name="roles"
          render={({ field }) => (
            <div className="space-y-2">
              <SearchableMultiSelect
                id="roles"
                label="IT-роли"
                options={roleOptions.map((option) => ({ value: option.id, label: option.title }))}
                value={field.value}
                onChange={field.onChange}
                placeholder="Выберите до пяти ролей"
                searchPlaceholder="Найти роль"
                maxSelections={5}
              />
              {form.formState.errors.roles ? <p className="text-sm text-destructive">{form.formState.errors.roles.message}</p> : null}
            </div>
          )}
        />

        <div className="space-y-2">
          <Label htmlFor="about">О себе</Label>
          <Textarea id="about" placeholder="Коротко о задачах, интересах и сильных сторонах" {...form.register('about')} />
          {form.formState.errors.about ? <p className="text-sm text-destructive">{form.formState.errors.about.message}</p> : null}
        </div>

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
