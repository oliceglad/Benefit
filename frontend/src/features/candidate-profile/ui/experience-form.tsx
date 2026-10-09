import { zodResolver } from '@hookform/resolvers/zod'
import { ChevronDown, Plus, Trash2 } from 'lucide-react'
import { useCallback, useState, type ReactNode } from 'react'
import { Controller, useFieldArray, useForm, useWatch } from 'react-hook-form'

import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import { useRegisterProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import { buildExperienceUpdate } from '@/features/candidate-profile/model/profile-updates'
import {
  educationLevelSchema,
  experienceSchema,
  type ExperienceValues,
} from '@/features/candidate-profile/model/profile-schemas'
import { useProfileSectionSave } from '@/features/candidate-profile/model/use-profile-section-save'
import {
  SaveState,
  SectionActions,
  SectionFormCard,
} from '@/features/candidate-profile/ui/section-form-layout'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { Checkbox } from '@/shared/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/ui/collapsible'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { MonthPicker } from '@/shared/ui/month-picker'
import { SelectField } from '@/shared/ui/select-field'
import { Textarea } from '@/shared/ui/textarea'

type CollectionName = 'experience' | 'education' | 'courses' | 'projects'
type PendingDelete = { collection: CollectionName; index: number } | null

function month(value?: string | null): string {
  return value ? value.slice(0, 7) : ''
}

function valuesFromProfile(profile: ProfileResponse): ExperienceValues {
  return {
    experience: profile.experience.map((item) => ({
      company: item.company,
      position: item.position,
      startDate: month(item.start_date),
      endDate: month(item.end_date),
      current: !item.end_date,
      city: item.city ?? '',
      description: item.description ?? '',
      achievements: (item.achievements ?? []).join('\n'),
      technologies: (item.technologies ?? []).join(', '),
    })),
    education: profile.education.map((item) => ({
      institution: item.institution,
      level: item.level ?? '',
      faculty: item.faculty ?? '',
      specialization: item.specialization ?? '',
      graduationYear: item.graduation_year == null ? '' : String(item.graduation_year),
    })),
    courses: profile.courses.map((item) => ({
      name: item.name,
      organization: item.organization ?? '',
      year: item.year == null ? '' : String(item.year),
      url: item.url ?? '',
    })),
    projects: profile.projects.map((item) => ({
      name: item.name,
      role: item.role ?? '',
      description: item.description ?? '',
      url: item.url ?? '',
      technologies: (item.technologies ?? []).join(', '),
    })),
  }
}

export function ExperienceForm({
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
  const form = useForm<ExperienceValues>({
    resolver: zodResolver(experienceSchema),
    defaultValues: valuesFromProfile(profile),
  })
  const experience = useFieldArray({ control: form.control, name: 'experience' })
  const education = useFieldArray({ control: form.control, name: 'education' })
  const courses = useFieldArray({ control: form.control, name: 'courses' })
  const projects = useFieldArray({ control: form.control, name: 'projects' })
  const watchedExperience = useWatch({ control: form.control, name: 'experience' })
  const watchedEducation = useWatch({ control: form.control, name: 'education' })
  const watchedCourses = useWatch({ control: form.control, name: 'courses' })
  const watchedProjects = useWatch({ control: form.control, name: 'projects' })
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null)
  const applyProfile = useCallback(
    (next: ProfileResponse) => form.reset(valuesFromProfile(next)),
    [form],
  )
  const save = useProfileSectionSave({ profile, isDirty: form.formState.isDirty, applyProfile })

  async function saveForm(): Promise<boolean> {
    if (!form.formState.isDirty) return true
    let succeeded = false
    await form.handleSubmit(async (values) => {
      succeeded = await save.save(buildExperienceUpdate(values))
    })()
    return succeeded
  }

  useRegisterProfileDraft(
    'experience',
    form.formState.isDirty,
    saveForm,
    () => form.reset(valuesFromProfile(profile)),
  )

  function removePending(): void {
    if (!pendingDelete) return
    if (pendingDelete.collection === 'experience') experience.remove(pendingDelete.index)
    if (pendingDelete.collection === 'education') education.remove(pendingDelete.index)
    if (pendingDelete.collection === 'courses') courses.remove(pendingDelete.index)
    if (pendingDelete.collection === 'projects') projects.remove(pendingDelete.index)
    setPendingDelete(null)
  }

  return (
    <SectionFormCard
      title="Опыт и образование"
      description="Добавляйте актуальные места работы, образование, курсы и проекты."
      standalone={standalone}
    >
      <form className="space-y-8" noValidate onSubmit={(event) => event.preventDefault()}>
        <SaveState confirmation={save.confirmation} error={save.error} dirty={form.formState.isDirty} retrying={save.isRetryingConfirmation} onRetry={() => void save.retryConfirmation().then((ok) => { if (ok && standalone) onContinue() })} />

        <RepeatedHeader title="Опыт работы" addLabel="Добавить место работы" onAdd={() => experience.append({ company: '', position: '', startDate: '', endDate: '', current: false, city: '', description: '', achievements: '', technologies: '' })} />
        {experience.fields.length === 0 ? <EmptyText>Можно сохранить профиль без опыта работы.</EmptyText> : null}
        {experience.fields.map((field, index) => (
          <RecordCard
            key={field.id}
            title={watchedExperience[index]?.position || `Место работы ${index + 1}`}
            subtitle={[watchedExperience[index]?.company, experiencePeriod(watchedExperience[index])].filter(Boolean).join(' · ')}
            defaultOpen={!watchedExperience[index]?.position && !watchedExperience[index]?.company}
            deleteLabel="Удалить место работы"
            onDelete={() => setPendingDelete({ collection: 'experience', index })}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id={`company-${index}`} label="Компания" error={form.formState.errors.experience?.[index]?.company?.message}><Input id={`company-${index}`} {...form.register(`experience.${index}.company`)} /></Field>
              <Field id={`position-${index}`} label="Должность" error={form.formState.errors.experience?.[index]?.position?.message}><Input id={`position-${index}`} {...form.register(`experience.${index}.position`)} /></Field>
              <Field id={`experience-start-${index}-year`} label="Начало" error={form.formState.errors.experience?.[index]?.startDate?.message}>
                <Controller
                  control={form.control}
                  name={`experience.${index}.startDate`}
                  render={({ field: startField, fieldState }) => (
                    <MonthPicker
                      id={`experience-start-${index}`}
                      value={startField.value}
                      onValueChange={startField.onChange}
                      invalid={fieldState.invalid}
                    />
                  )}
                />
              </Field>
              <Field id={`experience-end-${index}-year`} label="Окончание" error={form.formState.errors.experience?.[index]?.endDate?.message}>
                <Controller
                  control={form.control}
                  name={`experience.${index}.endDate`}
                  render={({ field: endField, fieldState }) => (
                    <MonthPicker
                      id={`experience-end-${index}`}
                      value={endField.value}
                      onValueChange={endField.onChange}
                      disabled={watchedExperience[index]?.current}
                      invalid={fieldState.invalid}
                    />
                  )}
                />
              </Field>
              <Controller
                control={form.control}
                name={`experience.${index}.current`}
                render={({ field: currentField }) => (
                  <label className="flex min-h-11 cursor-pointer items-center gap-3 py-2 text-sm transition-colors hover:text-primary sm:col-span-2">
                    <Checkbox
                      checked={currentField.value}
                      onCheckedChange={(checked) => {
                        const isCurrent = checked === true
                        currentField.onChange(isCurrent)
                        if (isCurrent) {
                          form.setValue(`experience.${index}.endDate`, '', {
                            shouldDirty: true,
                            shouldValidate: true,
                          })
                          form.clearErrors(`experience.${index}.endDate`)
                        }
                      }}
                    />
                    Работаю сейчас
                  </label>
                )}
              />
              <Field id={`experience-city-${index}`} label="Город"><Input id={`experience-city-${index}`} {...form.register(`experience.${index}.city`)} /></Field>
              <Field id={`experience-tech-${index}`} label="Технологии через запятую"><Input id={`experience-tech-${index}`} {...form.register(`experience.${index}.technologies`)} /></Field>
              <Field id={`experience-description-${index}`} label="Описание" className="sm:col-span-2"><Textarea id={`experience-description-${index}`} {...form.register(`experience.${index}.description`)} /></Field>
              <Field id={`experience-achievements-${index}`} label="Достижения — каждое с новой строки" className="sm:col-span-2"><Textarea id={`experience-achievements-${index}`} {...form.register(`experience.${index}.achievements`)} /></Field>
            </div>
          </RecordCard>
        ))}

        <RepeatedHeader title="Образование" addLabel="Добавить образование" onAdd={() => education.append({ institution: '', level: '', faculty: '', specialization: '', graduationYear: '' })} />
        {education.fields.length === 0 ? <EmptyText>Образование пока не добавлено.</EmptyText> : null}
        {education.fields.map((field, index) => (
          <RecordCard key={field.id} title={watchedEducation[index]?.institution || `Образование ${index + 1}`} subtitle={[watchedEducation[index]?.specialization, watchedEducation[index]?.graduationYear].filter(Boolean).join(' · ')} defaultOpen={!watchedEducation[index]?.institution} deleteLabel="Удалить образование" onDelete={() => setPendingDelete({ collection: 'education', index })}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id={`institution-${index}`} label="Учебное заведение" error={form.formState.errors.education?.[index]?.institution?.message} className="sm:col-span-2"><Input id={`institution-${index}`} {...form.register(`education.${index}.institution`)} /></Field>
              <Field id={`education-level-${index}`} label="Уровень">
                <Controller
                  control={form.control}
                  name={`education.${index}.level`}
                  render={({ field: levelField }) => (
                    <SelectField
                      id={`education-level-${index}`}
                      value={levelField.value}
                      onValueChange={levelField.onChange}
                      options={[
                        { value: '', label: 'Не указан' },
                        ...dictionaries.education_levels
                          .filter((option) => educationLevelSchema.safeParse(option.id).success)
                          .map((option) => ({ value: option.id, label: option.title })),
                      ]}
                    />
                  )}
                />
              </Field>
              <Field id={`graduation-${index}`} label="Год окончания" error={form.formState.errors.education?.[index]?.graduationYear?.message}><Input id={`graduation-${index}`} inputMode="numeric" maxLength={4} placeholder="Например, 2024" {...form.register(`education.${index}.graduationYear`)} /></Field>
              <Field id={`faculty-${index}`} label="Факультет"><Input id={`faculty-${index}`} {...form.register(`education.${index}.faculty`)} /></Field>
              <Field id={`edu-specialization-${index}`} label="Специальность"><Input id={`edu-specialization-${index}`} {...form.register(`education.${index}.specialization`)} /></Field>
            </div>
          </RecordCard>
        ))}

        <RepeatedHeader title="Курсы" addLabel="Добавить курс" onAdd={() => courses.append({ name: '', organization: '', year: '', url: '' })} />
        {courses.fields.length === 0 ? <EmptyText>Курсы пока не добавлены.</EmptyText> : null}
        {courses.fields.map((field, index) => (
          <RecordCard key={field.id} title={watchedCourses[index]?.name || `Курс ${index + 1}`} subtitle={watchedCourses[index]?.organization} defaultOpen={!watchedCourses[index]?.name} deleteLabel="Удалить курс" onDelete={() => setPendingDelete({ collection: 'courses', index })}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id={`course-name-${index}`} label="Название" error={form.formState.errors.courses?.[index]?.name?.message}><Input id={`course-name-${index}`} {...form.register(`courses.${index}.name`)} /></Field>
              <Field id={`course-org-${index}`} label="Организация"><Input id={`course-org-${index}`} {...form.register(`courses.${index}.organization`)} /></Field>
              <Field id={`course-year-${index}`} label="Год" error={form.formState.errors.courses?.[index]?.year?.message}><Input id={`course-year-${index}`} inputMode="numeric" maxLength={4} placeholder="Например, 2024" {...form.register(`courses.${index}.year`)} /></Field>
              <Field id={`course-url-${index}`} label="Ссылка" error={form.formState.errors.courses?.[index]?.url?.message}><Input id={`course-url-${index}`} type="url" {...form.register(`courses.${index}.url`)} /></Field>
            </div>
          </RecordCard>
        ))}

        <RepeatedHeader title="Проекты" addLabel="Добавить проект" onAdd={() => projects.append({ name: '', role: '', description: '', url: '', technologies: '' })} />
        {projects.fields.length === 0 ? <EmptyText>Проекты пока не добавлены.</EmptyText> : null}
        {projects.fields.map((field, index) => (
          <RecordCard key={field.id} title={watchedProjects[index]?.name || `Проект ${index + 1}`} subtitle={watchedProjects[index]?.role} defaultOpen={!watchedProjects[index]?.name} deleteLabel="Удалить проект" onDelete={() => setPendingDelete({ collection: 'projects', index })}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id={`project-name-${index}`} label="Название" error={form.formState.errors.projects?.[index]?.name?.message}><Input id={`project-name-${index}`} {...form.register(`projects.${index}.name`)} /></Field>
              <Field id={`project-role-${index}`} label="Роль"><Input id={`project-role-${index}`} {...form.register(`projects.${index}.role`)} /></Field>
              <Field id={`project-url-${index}`} label="Ссылка" error={form.formState.errors.projects?.[index]?.url?.message}><Input id={`project-url-${index}`} type="url" {...form.register(`projects.${index}.url`)} /></Field>
              <Field id={`project-tech-${index}`} label="Технологии через запятую"><Input id={`project-tech-${index}`} {...form.register(`projects.${index}.technologies`)} /></Field>
              <Field id={`project-description-${index}`} label="Описание" className="sm:col-span-2"><Textarea id={`project-description-${index}`} {...form.register(`projects.${index}.description`)} /></Field>
            </div>
          </RecordCard>
        ))}

        <SectionActions dirty={form.formState.isDirty} pending={save.isPending} hasNext={!standalone} onSave={() => void saveForm().then((ok) => { if (ok && standalone) onContinue() })} onSaveAndContinue={() => void saveForm().then((ok) => { if (ok) onContinue() })} />
      </form>

      <AlertDialog open={pendingDelete !== null} onOpenChange={(open) => { if (!open) setPendingDelete(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить запись?</AlertDialogTitle>
            <AlertDialogDescription>Запись будет удалена после сохранения раздела. До сохранения это действие можно отменить, покинув раздел без изменений.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive !text-white hover:bg-destructive/90" onClick={removePending}>Удалить</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SectionFormCard>
  )
}

function RepeatedHeader({ title, addLabel, onAdd }: { title: string; addLabel: string; onAdd: () => void }) {
  return <div className="space-y-3 border-t pt-7 first:border-0 first:pt-0"><h3 className="text-lg font-semibold">{title}</h3><Button type="button" size="sm" variant="ghost" className="px-0 text-primary hover:bg-transparent" onClick={onAdd}><Plus aria-hidden="true" />{addLabel}</Button></div>
}

function RecordCard({ title, subtitle, defaultOpen, deleteLabel, onDelete, children }: { title: string; subtitle?: string; defaultOpen: boolean; deleteLabel: string; onDelete: () => void; children: ReactNode }) {
  return (
    <Collapsible defaultOpen={defaultOpen} className="rounded-xl border bg-card">
      <div className="flex min-w-0 items-center gap-2 p-2 sm:p-3">
        <CollapsibleTrigger className="group flex min-h-10 min-w-0 flex-1 items-center gap-2 rounded-lg px-2 text-left font-semibold outline-none transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40">
          <ChevronDown className="size-4 shrink-0 transition-transform group-data-[state=closed]:-rotate-90" aria-hidden="true" />
          <span className="min-w-0">
            <span className="block break-words">{title}</span>
            {subtitle ? <span className="mt-0.5 block break-words text-xs font-normal text-muted-foreground">{subtitle}</span> : null}
          </span>
        </CollapsibleTrigger>
        <Button type="button" variant="ghost" size="sm" className="text-destructive hover:bg-destructive/10 hover:text-destructive" aria-label={deleteLabel} onClick={onDelete}>
          <Trash2 aria-hidden="true" />
          <span className="hidden sm:inline">Удалить</span>
        </Button>
      </div>
      <CollapsibleContent>
        <div className="border-t p-4 sm:p-5">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
}

function EmptyText({ children }: { children: string }) {
  return <p className="text-sm leading-6 text-muted-foreground">{children}</p>
}

function experiencePeriod(value: ExperienceValues['experience'][number] | undefined): string {
  if (!value?.startDate) return ''
  return `${value.startDate} — ${value.current ? 'сейчас' : value.endDate || 'не указано'}`
}

function Field({ id, label, error, className, children }: { id: string; label: string; error?: string; className?: string; children: ReactNode }) {
  return <div className={`space-y-1.5 ${className ?? ''}`}><Label htmlFor={id}>{label}</Label>{children}{error ? <p className="text-sm text-destructive">{error}</p> : null}</div>
}
