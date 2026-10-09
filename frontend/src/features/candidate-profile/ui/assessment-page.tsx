import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { AlertCircle, BadgeCheck, Clock3, FileQuestion, History, RotateCcw } from 'lucide-react'
import { Controller, useForm, useWatch } from 'react-hook-form'

import {
  assessmentAttemptQueryKey,
  assessmentCatalogQueryKey,
  assessmentHistoryQueryKey,
  assessmentStatusQueryKey,
  assessmentSurveyQueryKey,
  getAssessmentCatalog,
  getAssessmentHistory,
  getAssessmentStatus,
  getAssessmentSurvey,
  startAssessment,
} from '@/features/candidate-profile/api/assessment'
import { parseLocalizedNumber } from '@/features/candidate-profile/model/form-values'
import { assessmentStartSchema, type AssessmentStartValues } from '@/features/candidate-profile/model/assessment-schema'
import type {
  AssessmentInfo,
  AssessmentStatus,
  AttemptSummary,
  SurveyOptions,
} from '@/shared/api/generated/assessments/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { SelectField } from '@/shared/ui/select-field'
import { Spinner } from '@/shared/ui/spinner'

const gradeLabels: Record<string, string> = {
  intern: 'Стажёр', junior: 'Junior', middle: 'Middle', senior: 'Senior', lead: 'Lead',
}

function durationLabel(seconds: number): string {
  const minutes = Math.ceil(seconds / 60)
  return minutes < 60 ? `${minutes} мин` : `${Math.floor(minutes / 60)} ч ${minutes % 60} мин`
}

export function AssessmentPage() {
  const navigate = useNavigate()
  const survey = useQuery({ queryKey: assessmentSurveyQueryKey, queryFn: ({ signal }) => getAssessmentSurvey(signal) })
  const catalog = useQuery({ queryKey: assessmentCatalogQueryKey, queryFn: ({ signal }) => getAssessmentCatalog(signal), staleTime: 5 * 60_000 })
  const status = useQuery({ queryKey: assessmentStatusQueryKey, queryFn: ({ signal }) => getAssessmentStatus(signal), staleTime: 30_000 })
  const history = useQuery({ queryKey: assessmentHistoryQueryKey, queryFn: ({ signal }) => getAssessmentHistory(signal), staleTime: 30_000 })
  const pending = survey.isPending || catalog.isPending || status.isPending || history.isPending
  const error = survey.error ?? catalog.error ?? status.error ?? history.error

  if (pending) return <Card className="min-h-80"><CardContent className="grid min-h-80 place-items-center"><Spinner label="Загружаем проверку…" /></CardContent></Card>
  if (error || !survey.data || !catalog.data || !status.data || !history.data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        <AlertTitle>Проверка не загрузилась</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{isApiError(error) ? error.message : 'Повторите попытку позже.'}</p>
          <Button type="button" size="sm" variant="outline" onClick={() => { void survey.refetch(); void catalog.refetch(); void status.refetch(); void history.refetch() }}><RotateCcw aria-hidden="true" />Повторить</Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold text-primary">Проверка знаний</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Подтверждение грейда</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Задания подбираются по специализации, грейду и навыкам профиля. Результат подтверждает общий грейд, а не отдельный навык.</p>
      </div>

      {status.data.active_attempt_id ? (
        <Alert variant="warning">
          <Clock3 className="size-4" aria-hidden="true" />
          <AlertTitle>Есть начатая попытка</AlertTitle>
          <AlertDescription className="mt-3">
            <Button type="button" size="sm" onClick={() => void navigate({ to: '/assessments/attempts/$attemptId', params: { attemptId: status.data.active_attempt_id as string } })}>Продолжить</Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {status.data.verified ? (
        <Alert variant="success">
          <BadgeCheck className="size-4" aria-hidden="true" />
          <AlertTitle>Подтверждённый грейд: {gradeLabels[status.data.verified.grade] ?? status.data.verified.grade}</AlertTitle>
          <AlertDescription>Результат {status.data.verified.percent}%. Действует до {new Intl.DateTimeFormat('ru-RU').format(new Date(status.data.verified.valid_until))}.</AlertDescription>
        </Alert>
      ) : null}

      <AssessmentStartForm survey={survey.data} catalog={catalog.data} status={status.data} />
      <AssessmentHistory attempts={history.data.filter((attempt) => !attempt.assignment_id)} />
    </section>
  )
}

function AssessmentStartForm({ survey, catalog, status }: { survey: SurveyOptions; catalog: AssessmentInfo[]; status: AssessmentStatus }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const form = useForm<AssessmentStartValues>({
    resolver: zodResolver(assessmentStartSchema),
    defaultValues: {
      industry: survey.prefill?.industry ?? undefined,
      specialization: survey.prefill?.specialization ?? undefined,
      targetGrade: survey.prefill?.claimed_grade ?? undefined,
      yearsOfExperience: survey.prefill?.years_of_experience == null ? '' : String(survey.prefill.years_of_experience).replace('.', ','),
    },
  })
  const specialization = useWatch({ control: form.control, name: 'specialization' })
  const targetGrade = useWatch({ control: form.control, name: 'targetGrade' })
  const specializationOption = survey.specializations.find((option) => option.id === specialization)
  const selectedTest = catalog.find((test) => test.specialization === specialization && test.grade === targetGrade)
  const cooldown = status.cooldowns.find((item) => item.specialization === specialization)
  const start = useMutation({
    mutationFn: startAssessment,
    onSuccess: async (attempt) => {
      queryClient.setQueryData(assessmentAttemptQueryKey(attempt.id), attempt)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: assessmentStatusQueryKey }),
        queryClient.invalidateQueries({ queryKey: assessmentHistoryQueryKey }),
      ])
      await navigate({ to: '/assessments/attempts/$attemptId', params: { attemptId: attempt.id } })
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Перед началом</CardTitle>
        <CardDescription>Выберите направление проверки. Таймер запустится только после нажатия «Начать проверку».</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-6" noValidate onSubmit={(event) => void form.handleSubmit((values) => start.mutate({
          industry: values.industry,
          specialization: values.specialization,
          target_grade: values.targetGrade,
          years_of_experience: parseLocalizedNumber(values.yearsOfExperience),
          skills: survey.prefill?.skills ?? [],
        }))(event)}>
          {start.isError ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Не удалось начать проверку</AlertTitle><AlertDescription>{isApiError(start.error) ? start.error.message : 'Повторите попытку.'}</AlertDescription></Alert> : null}
          <div className="grid gap-5 sm:grid-cols-2">
            <FormSelect control={form.control} name="industry" id="assessment-industry" label="Отрасль" placeholder="Выберите отрасль" options={survey.industries.map((option) => ({ value: option.id, label: option.title }))} />
            <Controller control={form.control} name="specialization" render={({ field, fieldState }) => <div className="space-y-2"><Label htmlFor="assessment-specialization">Специализация</Label><SelectField id="assessment-specialization" value={field.value ?? ''} onValueChange={(value) => { field.onChange(value); form.resetField('targetGrade') }} placeholder="Выберите специализацию" options={survey.specializations.filter((option) => option.grades.length > 0).map((option) => ({ value: option.id, label: option.title }))} invalid={fieldState.invalid} />{fieldState.error ? <p className="text-sm text-destructive">{fieldState.error.message}</p> : null}</div>} />
            <FormSelect control={form.control} name="targetGrade" id="assessment-grade" label="Грейд для подтверждения" placeholder="Выберите грейд" disabled={!specialization} options={(specializationOption?.grades ?? []).map((grade) => ({ value: grade, label: survey.grades.find((option) => option.id === grade)?.title ?? gradeLabels[grade] ?? grade }))} />
            <div className="space-y-2"><Label htmlFor="assessment-experience">Стаж, лет</Label><Input id="assessment-experience" inputMode="decimal" placeholder="Например, 2,5" aria-invalid={Boolean(form.formState.errors.yearsOfExperience)} {...form.register('yearsOfExperience')} />{form.formState.errors.yearsOfExperience ? <p className="text-sm text-destructive">{form.formState.errors.yearsOfExperience.message}</p> : null}</div>
          </div>

          {selectedTest ? (
            <div className="grid gap-3 rounded-xl bg-muted p-4 sm:grid-cols-3">
              <Condition icon={FileQuestion} label="Что проверяется" value={`${selectedTest.title}. ${selectedTest.tasks_per_attempt} заданий`} />
              <Condition icon={Clock3} label="Время" value={durationLabel(selectedTest.time_limit_seconds)} />
              <Condition icon={History} label="Результат" value={`Для подтверждения грейда требуется ${survey.pass_percent}%`} />
              {selectedTest.description ? <p className="text-sm leading-6 text-muted-foreground sm:col-span-3">{selectedTest.description}</p> : null}
            </div>
          ) : specialization && targetGrade ? (
            <Alert variant="warning"><FileQuestion className="size-4" aria-hidden="true" /><AlertTitle>Заданий пока нет</AlertTitle><AlertDescription>Для выбранной специализации и грейда проверка ещё не подготовлена.</AlertDescription></Alert>
          ) : null}

          {cooldown ? <Alert variant="warning"><Clock3 className="size-4" aria-hidden="true" /><AlertTitle>Повторная попытка пока недоступна</AlertTitle><AlertDescription>Можно начать {new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(cooldown.available_at))}.</AlertDescription></Alert> : null}
          <div className="flex justify-end border-t pt-5"><Button type="submit" disabled={start.isPending || Boolean(status.active_attempt_id) || !selectedTest || Boolean(cooldown)}>{start.isPending ? <Spinner label="Начинаем…" /> : 'Начать проверку'}</Button></div>
        </form>
      </CardContent>
    </Card>
  )
}

type AssessmentFormControl = ReturnType<typeof useForm<AssessmentStartValues>>['control']
function FormSelect({ control, name, id, label, options, placeholder, disabled = false }: { control: AssessmentFormControl; name: 'industry' | 'targetGrade'; id: string; label: string; options: { value: string; label: string }[]; placeholder: string; disabled?: boolean }) {
  return <Controller control={control} name={name} render={({ field, fieldState }) => <div className="space-y-2"><Label htmlFor={id}>{label}</Label><SelectField id={id} value={field.value ?? ''} onValueChange={field.onChange} options={options} placeholder={placeholder} disabled={disabled} invalid={fieldState.invalid} />{fieldState.error ? <p className="text-sm text-destructive">{fieldState.error.message}</p> : null}</div>} />
}

function Condition({ icon: Icon, label, value }: { icon: typeof Clock3; label: string; value: string }) {
  return <div className="flex items-start gap-2"><Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-0.5 text-sm font-medium">{value}</p></div></div>
}

function AssessmentHistory({ attempts }: { attempts: AttemptSummary[] }) {
  const navigate = useNavigate()
  if (attempts.length === 0) return null
  return (
    <Card>
      <CardHeader><CardTitle>История попыток</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {attempts.map((attempt) => <div key={attempt.id} className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">{attempt.title}</p><p className="mt-1 text-xs text-muted-foreground">{new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(attempt.started_at))}{attempt.percent == null ? '' : ` · ${attempt.percent}%`}</p></div><div className="flex items-center gap-2"><Badge variant={attempt.status === 'in_progress' ? 'secondary' : attempt.confirmed_grade ? 'success' : 'secondary'}>{attempt.status === 'in_progress' ? 'Идёт' : attempt.confirmed_grade ? 'Грейд подтверждён' : 'Завершена'}</Badge><Button type="button" size="sm" variant="outline" onClick={() => void navigate({ to: '/assessments/attempts/$attemptId', params: { attemptId: attempt.id } })}>{attempt.status === 'in_progress' ? 'Продолжить' : 'Посмотреть результат'}</Button></div></div>)}
      </CardContent>
    </Card>
  )
}
