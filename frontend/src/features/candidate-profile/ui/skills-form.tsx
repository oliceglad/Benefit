import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { ChevronUp, Pencil, Search, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useId, useMemo, useState } from 'react'
import { Controller, useFieldArray, useForm, useWatch } from 'react-hook-form'

import { searchProfileSkills } from '@/features/candidate-profile/api/profile'
import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import { useRegisterProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import { buildSkillVerificationState } from '@/features/candidate-profile/model/skill-verification'
import { useAssessmentOverview } from '@/features/candidate-profile/model/use-assessment-overview'
import { buildSkillsUpdate, withoutSelectedSkills } from '@/features/candidate-profile/model/profile-updates'
import {
  languageLevelSchema,
  skillLevelSchema,
  skillsSchema,
  type SkillsValues,
} from '@/features/candidate-profile/model/profile-schemas'
import { useProfileSectionSave } from '@/features/candidate-profile/model/use-profile-section-save'
import {
  SaveState,
  SectionActions,
  SectionFormCard,
} from '@/features/candidate-profile/ui/section-form-layout'
import { SearchableMultiSelect } from '@/features/candidate-profile/ui/searchable-multi-select'
import { SkillVerificationPanel } from '@/features/candidate-profile/ui/skill-verification-panel'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
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
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { SelectField } from '@/shared/ui/select-field'
import { Spinner } from '@/shared/ui/spinner'

function valuesFromProfile(profile: ProfileResponse): SkillsValues {
  return {
    skills: profile.skills.map((skill) => ({
      name: skill.name,
      level: skill.level ?? '',
      years: skill.years == null ? '' : String(skill.years),
    })),
    softSkills: profile.soft_skills,
    languages: profile.languages,
  }
}

function useDebouncedValue(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timeout)
  }, [delay, value])
  return debounced
}

export function SkillsForm({
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
  const form = useForm<SkillsValues>({
    resolver: zodResolver(skillsSchema),
    defaultValues: valuesFromProfile(profile),
  })
  const skills = useFieldArray({ control: form.control, name: 'skills' })
  const languages = useFieldArray({ control: form.control, name: 'languages' })
  const watchedSkills = useWatch({ control: form.control, name: 'skills' })
  const watchedLanguages = useWatch({ control: form.control, name: 'languages' })
  const [editingSkill, setEditingSkill] = useState<number | null>(null)
  const [editingLanguage, setEditingLanguage] = useState<number | null>(null)
  const [pendingDelete, setPendingDelete] = useState<{ kind: 'skill' | 'language'; index: number; title: string } | null>(null)
  const navigate = useNavigate()
  const assessment = useAssessmentOverview()
  const applyProfile = useCallback(
    (next: ProfileResponse) => form.reset(valuesFromProfile(next)),
    [form],
  )
  const save = useProfileSectionSave({ profile, isDirty: form.formState.isDirty, applyProfile })

  async function saveForm(): Promise<boolean> {
    if (!form.formState.isDirty) return true
    let succeeded = false
    await form.handleSubmit(async (values) => {
      succeeded = await save.save(buildSkillsUpdate(values))
    })()
    return succeeded
  }

  useRegisterProfileDraft(
    'skills',
    form.formState.isDirty,
    saveForm,
    () => form.reset(valuesFromProfile(profile)),
  )

  async function openAssessment(attemptId?: string): Promise<void> {
    const saved = await saveForm()
    if (!saved) return
    if (attemptId) {
      await navigate({ to: '/assessments/attempts/$attemptId', params: { attemptId } })
    } else {
      await navigate({ to: '/assessments' })
    }
  }

  function openSkillAssessment(index: number, fallbackName: string): void {
    const attemptId = assessment.status?.active_attempt_id
      ?? assessment.attempts.find((attempt) => attempt.result?.skills.some((score) => score.skill.localeCompare(watchedSkills[index]?.name ?? fallbackName, 'ru-RU', { sensitivity: 'accent' }) === 0))?.id
    void openAssessment(attemptId ?? undefined)
  }

  const verificationStates = skills.fields.map((field, index) => buildSkillVerificationState({
    skill: watchedSkills[index]?.name ?? field.name,
    dirty: form.formState.isDirty,
    loading: assessment.loading,
    failed: assessment.failed,
    profileRoles: profile.roles,
    profileGrade: profile.grade,
    catalog: assessment.catalog,
    status: assessment.status,
    attempts: assessment.attempts,
  }))
  function confirmDelete(): void {
    if (!pendingDelete) return
    if (pendingDelete.kind === 'skill') {
      skills.remove(pendingDelete.index)
      setEditingSkill(null)
    } else {
      languages.remove(pendingDelete.index)
      setEditingLanguage(null)
    }
    setPendingDelete(null)
  }

  return (
    <SectionFormCard
      title="Навыки и языки"
      description="Добавьте навыки и укажите уровень владения и стаж."
      standalone={standalone}
    >
      <form className="space-y-7" noValidate onSubmit={(event) => event.preventDefault()}>
        <SaveState confirmation={save.confirmation} error={save.error} dirty={form.formState.isDirty} retrying={save.isRetryingConfirmation} onRetry={() => void save.retryConfirmation().then((ok) => { if (ok && standalone) onContinue() })} />
        <SkillSearch
          selected={watchedSkills.map((skill) => skill.name)}
          onSelect={(name) => {
            const index = skills.fields.length
            skills.append({ name, level: '', years: '' })
            setEditingSkill(index)
          }}
        />

        <section className="space-y-3" aria-labelledby="technical-skills-title">
          <h3 id="technical-skills-title" className="text-lg font-semibold">Технические навыки</h3>
          {skills.fields.length === 0 ? (
            <p className="text-sm leading-6 text-muted-foreground">Навыки пока не добавлены.</p>
          ) : skills.fields.map((field, index) => (
            <article key={field.id} className="rounded-xl border bg-card p-4">
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="break-words text-base font-semibold">{watchedSkills[index]?.name}</h3>
                  <p className="mt-1 break-words text-sm text-muted-foreground">{skillSummary(watchedSkills[index], dictionaries)}</p>
                  {verificationStates[index] && verificationStates[index].kind !== 'unsaved' ? <p className="mt-1 text-xs font-medium text-muted-foreground">{verificationStates[index].title}</p> : null}
                </div>
                <Button type="button" variant="ghost" size="sm" className="shrink-0" aria-expanded={editingSkill === index} onClick={() => setEditingSkill((current) => current === index ? null : index)}>
                  {editingSkill === index ? <ChevronUp aria-hidden="true" /> : <Pencil aria-hidden="true" />}
                  {editingSkill === index ? 'Скрыть' : 'Изменить'}
                </Button>
              </div>
              {editingSkill === index ? <div className="mt-4 space-y-4 border-t pt-4">
                <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_140px]">
                <div className="space-y-1.5">
                  <Label htmlFor={`skill-level-${index}`}>Уровень по вашей оценке</Label>
                  <Controller
                    control={form.control}
                    name={`skills.${index}.level`}
                    render={({ field: levelField }) => (
                      <SelectField
                        id={`skill-level-${index}`}
                        value={levelField.value}
                        onValueChange={levelField.onChange}
                        options={[
                          { value: '', label: 'Не указан' },
                          ...dictionaries.skill_levels
                            .filter((option) => skillLevelSchema.safeParse(option.id).success)
                            .map((option) => ({ value: option.id, label: option.title })),
                        ]}
                      />
                    )}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`skill-years-${index}`}>Лет опыта</Label>
                  <Input id={`skill-years-${index}`} inputMode="decimal" {...form.register(`skills.${index}.years`)} />
                </div>
              </div>
              {form.formState.errors.skills?.[index]?.years ? (
                <p className="text-sm text-destructive">{form.formState.errors.skills[index]?.years?.message}</p>
              ) : null}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button type="button" size="sm" variant="ghost" className="text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => setPendingDelete({ kind: 'skill', index, title: watchedSkills[index]?.name ?? field.name })}><Trash2 aria-hidden="true" />Удалить</Button>
                <SkillVerificationPanel state={verificationStates[index]} pending={save.isPending} onAction={() => openSkillAssessment(index, field.name)} />
              </div>
              </div> : null}
            </article>
          ))}
        </section>

        <Controller
          control={form.control}
          name="softSkills"
          render={({ field }) => (
            <SearchableMultiSelect
              id="soft-skills"
              label="Гибкие навыки"
              options={dictionaries.soft_skills.map((skill) => ({ value: skill, label: skill }))}
              value={field.value}
              onChange={field.onChange}
              placeholder="Выберите гибкие навыки"
              searchPlaceholder="Найти навык"
              maxSelections={30}
            />
          )}
        />

        <div className="space-y-3">
          <h3 className="text-lg font-semibold">Языки</h3>
          {languages.fields.map((field, index) => (
            <article key={field.id} className="rounded-xl border p-4">
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="min-w-0"><h4 className="break-words font-semibold">{watchedLanguages[index]?.language || `Язык ${index + 1}`}</h4><p className="mt-1 text-sm text-muted-foreground">{languageLevelTitle(watchedLanguages[index]?.level, dictionaries)}</p></div>
                <Button type="button" variant="ghost" size="sm" className="shrink-0" aria-expanded={editingLanguage === index} onClick={() => setEditingLanguage((current) => current === index ? null : index)}>
                  {editingLanguage === index ? <ChevronUp aria-hidden="true" /> : <Pencil aria-hidden="true" />}
                  {editingLanguage === index ? 'Скрыть' : 'Изменить'}
                </Button>
              </div>
              {editingLanguage === index ? <div className="mt-4 space-y-4 border-t pt-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor={`language-${index}`}>Язык</Label>
                  <Controller
                    control={form.control}
                    name={`languages.${index}.language`}
                    render={({ field: languageField }) => (
                      <SelectField
                        id={`language-${index}`}
                        value={languageField.value}
                        onValueChange={languageField.onChange}
                        options={dictionaries.languages.map((language) => ({ value: language, label: language }))}
                        placeholder="Выберите язык"
                      />
                    )}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`language-level-${index}`}>Уровень</Label>
                  <Controller
                    control={form.control}
                    name={`languages.${index}.level`}
                    render={({ field: levelField }) => (
                      <SelectField
                        id={`language-level-${index}`}
                        value={levelField.value}
                        onValueChange={levelField.onChange}
                        options={dictionaries.language_levels
                          .filter((option) => languageLevelSchema.safeParse(option.id).success)
                          .map((option) => ({ value: option.id, label: option.title }))}
                      />
                    )}
                  />
                </div>
              </div>
              {form.formState.errors.languages?.[index]?.language ? (
                <p className="text-sm text-destructive">{form.formState.errors.languages[index]?.language?.message}</p>
              ) : null}
              <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="ghost" className="text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => setPendingDelete({ kind: 'language', index, title: watchedLanguages[index]?.language || `Язык ${index + 1}` })}><Trash2 aria-hidden="true" />Удалить</Button></div>
              </div> : null}
            </article>
          ))}
          {languages.fields.length === 0 ? <p className="text-sm leading-6 text-muted-foreground">Языки пока не добавлены.</p> : null}
          <Button type="button" size="sm" variant="ghost" className="px-0 text-primary hover:bg-transparent" onClick={() => { const index = languages.fields.length; languages.append({ language: '', level: 'A1' }); setEditingLanguage(index) }}>
            Добавить язык
          </Button>
        </div>

        <SectionActions
          dirty={form.formState.isDirty}
          pending={save.isPending}
          hasNext={!standalone}
          onSave={() => void saveForm().then((ok) => { if (ok && standalone) onContinue() })}
          onSaveAndContinue={() => void saveForm().then((ok) => { if (ok) onContinue() })}
        />
      </form>

      <AlertDialog open={pendingDelete !== null} onOpenChange={(open) => { if (!open) setPendingDelete(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Удалить «{pendingDelete?.title}»?</AlertDialogTitle><AlertDialogDescription>Запись будет удалена после сохранения всего раздела.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction className="bg-destructive !text-white hover:bg-destructive/90" onClick={confirmDelete}>Удалить</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SectionFormCard>
  )
}

function skillSummary(skill: SkillsValues['skills'][number] | undefined, dictionaries: ProfileDictionaries): string {
  if (!skill) return 'Самооценка не указана'
  const level = dictionaries.skill_levels.find((option) => option.id === skill.level)?.title ?? 'Уровень не указан'
  const years = skill.years ? `${skill.years} ${skill.years === '1' ? 'год' : 'года'} опыта` : 'стаж не указан'
  return `${level} · ${years}`
}

function languageLevelTitle(level: string | undefined, dictionaries: ProfileDictionaries): string {
  return dictionaries.language_levels.find((option) => option.id === level)?.title ?? 'Уровень не указан'
}

function SkillSearch({ selected, onSelect }: { selected: string[]; onSelect: (name: string) => void }) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const result = useQuery({
    queryKey: ['candidate', 'skill-search', debouncedQuery],
    queryFn: ({ signal }) => searchProfileSkills(debouncedQuery, signal),
    enabled: debouncedQuery.length > 0,
    staleTime: 60_000,
  })
  const options = useMemo(() => withoutSelectedSkills(result.data ?? [], selected), [result.data, selected])

  function choose(name: string): void {
    onSelect(name)
    setQuery('')
  }

  const isOpen = query.trim().length > 0
  return (
    <div className="space-y-2">
      <Label htmlFor={`${listId}-input`}>Найти технический навык</Label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-muted-foreground" aria-hidden="true" />
        <Input
          id={`${listId}-input`}
          className="pl-9"
          value={query}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listId}
          aria-activedescendant={options[activeIndex] ? `${listId}-${activeIndex}` : undefined}
          placeholder="Например, TypeScript"
          onChange={(event) => { setQuery(event.target.value); setActiveIndex(0) }}
          onKeyDown={(event) => {
            if (!options.length) return
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setActiveIndex((current) => (current + 1) % options.length)
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActiveIndex((current) => (current - 1 + options.length) % options.length)
            } else if (event.key === 'Enter') {
              event.preventDefault()
              choose(options[activeIndex])
            } else if (event.key === 'Escape') {
              setQuery('')
            }
          }}
        />
        {isOpen ? (
          <div id={listId} role="listbox" className="absolute z-20 mt-1 grid max-h-56 w-full gap-1 overflow-auto rounded-lg border bg-popover p-1 shadow-lg">
            {result.isFetching ? <div className="p-3"><Spinner label="Ищем навыки…" /></div> : null}
            {result.isError ? (
              <Alert variant="destructive"><AlertTitle>Поиск недоступен</AlertTitle><AlertDescription>Повторите попытку позже.</AlertDescription></Alert>
            ) : null}
            {!result.isFetching && !result.isError && debouncedQuery && options.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground">Ничего не найдено</p>
            ) : null}
            {options.map((name, index) => (
              <button
                key={name}
                id={`${listId}-${index}`}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={`flex w-full rounded-md px-3 py-2 text-left text-sm ${index === activeIndex ? 'bg-accent' : 'hover:bg-accent'}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(name)}
              >
                {name}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">Выберите навык из подсказок.</p>
    </div>
  )
}
