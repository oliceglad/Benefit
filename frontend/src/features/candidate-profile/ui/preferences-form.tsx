import { zodResolver } from '@hookform/resolvers/zod'
import { Link2 } from 'lucide-react'
import { useCallback } from 'react'
import { Controller, useForm, useWatch, type Control } from 'react-hook-form'

import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import { formatSalary, parseSalary } from '@/features/candidate-profile/model/form-values'
import { useRegisterProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import {
  employmentTypeSchema,
  jobSearchStatusSchema,
  preferencesSchema,
  workFormatSchema,
  type PreferencesValues,
} from '@/features/candidate-profile/model/profile-schemas'
import { useProfileSectionSave } from '@/features/candidate-profile/model/use-profile-section-save'
import {
  SaveState,
  SectionActions,
  SectionFormCard,
} from '@/features/candidate-profile/ui/section-form-layout'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Checkbox } from '@/shared/ui/checkbox'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { SelectField } from '@/shared/ui/select-field'

function valuesFromProfile(profile: ProfileResponse): PreferencesValues {
  return {
    salaryFrom: profile.salary_from == null ? '' : formatSalary(String(profile.salary_from)),
    employmentTypes: profile.employment_types,
    workFormats: profile.work_formats,
    jobSearchStatus: profile.job_search_status,
    showBirthDate: profile.privacy.show_birth_date ?? false,
    showPhoto: profile.privacy.show_photo ?? false,
    showSalary: profile.privacy.show_salary ?? false,
    showFspAchievements: profile.privacy.show_fsp_achievements ?? false,
    hideCurrentCompany: profile.privacy.hide_current_company ?? false,
  }
}

export function PreferencesForm({
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
  const form = useForm<PreferencesValues>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: valuesFromProfile(profile),
  })
  const applyProfile = useCallback(
    (next: ProfileResponse) => form.reset(valuesFromProfile(next)),
    [form],
  )
  const save = useProfileSectionSave({ profile, isDirty: form.formState.isDirty, applyProfile })
  const employmentTypes = useWatch({ control: form.control, name: 'employmentTypes' })
  const workFormats = useWatch({ control: form.control, name: 'workFormats' })
  const employmentOptions = dictionaries.employment_types.flatMap((option) => {
    const parsed = employmentTypeSchema.safeParse(option.id)
    return parsed.success ? [{ ...option, id: parsed.data }] : []
  })
  const workFormatOptions = dictionaries.work_formats.flatMap((option) => {
    const parsed = workFormatSchema.safeParse(option.id)
    return parsed.success ? [{ ...option, id: parsed.data }] : []
  })

  async function saveForm(): Promise<boolean> {
    if (!form.formState.isDirty) return true
    let succeeded = false
    await form.handleSubmit(async (values) => {
      succeeded = await save.save({
        salary_from: values.salaryFrom === '' ? null : parseSalary(values.salaryFrom),
        salary_currency: 'RUB',
        employment_types: values.employmentTypes,
        work_formats: values.workFormats,
        job_search_status: values.jobSearchStatus,
        privacy: {
          show_birth_date: values.showBirthDate,
          show_photo: values.showPhoto,
          show_salary: values.showSalary,
          show_fsp_achievements: values.showFspAchievements,
          hide_current_company: values.hideCurrentCompany,
        },
      })
    })()
    return succeeded
  }

  useRegisterProfileDraft(
    'preferences',
    form.formState.isDirty,
    saveForm,
    () => form.reset(valuesFromProfile(profile)),
  )

  return (
    <SectionFormCard title="Предпочтения работы" description="Укажите условия, которые подходят вам, и настройте видимость опубликованного профиля." standalone={standalone}>
      <form className="space-y-7" noValidate onSubmit={(event) => event.preventDefault()}>
        <SaveState confirmation={save.confirmation} error={save.error} dirty={form.formState.isDirty} retrying={save.isRetryingConfirmation} onRetry={() => void save.retryConfirmation().then((ok) => { if (ok && standalone) onContinue() })} />
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="salary-from">Ожидания по зарплате, ₽</Label>
            <Controller
              control={form.control}
              name="salaryFrom"
              render={({ field }) => (
                <Input
                  id="salary-from"
                  ref={field.ref}
                  name={field.name}
                  value={field.value}
                  inputMode="numeric"
                  placeholder="Например, 180 000"
                  aria-invalid={Boolean(form.formState.errors.salaryFrom)}
                  onChange={field.onChange}
                  onBlur={() => {
                    field.onBlur()
                    const formatted = formatSalary(field.value)
                    if (formatted !== field.value) form.setValue('salaryFrom', formatted, { shouldDirty: true, shouldValidate: true })
                  }}
                />
              )}
            />
            {form.formState.errors.salaryFrom ? <p className="text-sm text-destructive">{form.formState.errors.salaryFrom.message}</p> : null}
            <p className="text-xs text-muted-foreground">Сумма указывается в рублях.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="job-status">Статус поиска</Label>
            <Controller
              control={form.control}
              name="jobSearchStatus"
              render={({ field }) => (
                <SelectField
                  id="job-status"
                  value={field.value}
                  onValueChange={field.onChange}
                  options={dictionaries.job_search_statuses
                    .filter((option) => jobSearchStatusSchema.safeParse(option.id).success)
                    .map((option) => ({ value: option.id, label: option.title }))}
                />
              )}
            />
          </div>
        </div>

        <ChoiceGroup
          title="Занятость"
          options={employmentOptions}
          value={employmentTypes}
          onChange={(value) => form.setValue('employmentTypes', value, { shouldDirty: true })}
        />
        <ChoiceGroup
          title="Формат работы"
          options={workFormatOptions}
          value={workFormats}
          onChange={(value) => form.setValue('workFormats', value, { shouldDirty: true })}
        />

        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold">Видимость профиля</legend>
          <div className="overflow-hidden rounded-xl border sm:grid sm:grid-cols-2">
            <PrivacyCheckbox control={form.control} name="showBirthDate" label="Показывать дату рождения" />
            <PrivacyCheckbox control={form.control} name="showPhoto" label="Показывать фото" />
            <PrivacyCheckbox control={form.control} name="showSalary" label="Показывать зарплату" />
            <PrivacyCheckbox control={form.control} name="showFspAchievements" label="Показывать достижения ФСП" />
            <PrivacyCheckbox control={form.control} name="hideCurrentCompany" label="Скрывать текущую компанию" />
          </div>
          <p className="text-xs leading-5 text-muted-foreground">Контакты открываются работодателю только после принятого приглашения или вашего отклика — они не управляются этими настройками.</p>
        </fieldset>

        {profile.fsp.linked ? (
          <Alert>
            <Link2 className="size-4" aria-hidden="true" />
            <AlertTitle>Профиль ФСП связан</AlertTitle>
            <AlertDescription>{profile.fsp.achievements.length > 0 ? `Достижений: ${profile.fsp.achievements.length}.` : 'Достижения пока не получены.'} Синхронизация и изменение подтверждённых данных выполняются отдельно.</AlertDescription>
          </Alert>
        ) : null}

        <SectionActions dirty={form.formState.isDirty} pending={save.isPending} hasNext={!standalone} onSave={() => void saveForm().then((ok) => { if (ok && standalone) onContinue() })} onSaveAndContinue={() => void saveForm().then((ok) => { if (ok) onContinue() })} />
      </form>
    </SectionFormCard>
  )
}

function ChoiceGroup<T extends string>({ title, options, value, onChange }: { title: string; options: { id: T; title: string }[]; value: T[]; onChange: (value: T[]) => void }) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-semibold">{title}</legend>
      <div className="overflow-hidden rounded-xl border sm:grid sm:grid-cols-2">
        {options.map((option) => {
          const checked = value.includes(option.id)
          return <label key={option.id} className="flex min-h-12 cursor-pointer items-center gap-3 border-b px-3 py-2.5 text-sm transition-colors last:border-b-0 hover:bg-muted/50 sm:[&:nth-last-child(-n+2)]:border-b-0 sm:[&:nth-child(odd)]:border-r"><Checkbox checked={checked} onCheckedChange={() => onChange(checked ? value.filter((item) => item !== option.id) : [...value, option.id])} />{option.title}</label>
        })}
      </div>
    </fieldset>
  )
}

function PrivacyCheckbox({ control, name, label }: { control: Control<PreferencesValues>; name: 'showBirthDate' | 'showPhoto' | 'showSalary' | 'showFspAchievements' | 'hideCurrentCompany'; label: string }) {
  return <Controller control={control} name={name} render={({ field }) => <label className="flex min-h-12 cursor-pointer items-center gap-3 border-b px-3 py-2.5 text-sm transition-colors last:border-b-0 hover:bg-muted/50 sm:[&:nth-last-child(-n+2)]:border-b-0 sm:[&:nth-child(odd)]:border-r"><Checkbox checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />{label}</label>} />
}
