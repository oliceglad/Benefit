import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import { AlertCircle, BadgeCheck, Check, CircleX, Clock3, Flag, SkipForward } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  assessmentAttemptQueryKey,
  assessmentHistoryQueryKey,
  assessmentStatusQueryKey,
  assessmentTaskQueryKey,
  finishAssessment,
  getAssessmentAttempt,
  getAssessmentTask,
  submitAssessmentAnswer,
} from '@/features/candidate-profile/api/assessment'
import type { AttemptResponse, TaskView } from '@/shared/api/generated/assessments/models'
import { isApiError } from '@/shared/api/transport/api-error'
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
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Checkbox } from '@/shared/ui/checkbox'
import { Progress } from '@/shared/ui/progress'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

const gradeLabels: Record<string, string> = {
  intern: 'Стажёр', junior: 'Junior', middle: 'Middle', senior: 'Senior', lead: 'Lead',
}

function useCountdown(target: number | null): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (target === null) return
    const interval = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(interval)
  }, [target])
  return target === null ? 0 : Math.max(0, Math.ceil((target - now) / 1000))
}

function clockLabel(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

export function AssessmentAttemptPage() {
  const { attemptId } = useParams({ from: '/_candidate/assessments/attempts/$attemptId' })
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmFinish, setConfirmFinish] = useState(false)
  const expiredRef = useRef(false)
  const attempt = useQuery({
    queryKey: assessmentAttemptQueryKey(attemptId),
    queryFn: ({ signal }) => getAssessmentAttempt(attemptId, signal),
    staleTime: 5_000,
  })
  const task = useQuery({
    queryKey: assessmentTaskQueryKey(attemptId),
    queryFn: ({ signal }) => getAssessmentTask(attemptId, signal),
    enabled: attempt.data?.status === 'in_progress',
    retry: false,
  })
  const overallLeft = useCountdown(attempt.data?.status === 'in_progress' ? Date.parse(attempt.data.deadline_at) : null)
  const taskDeadline = task.data
    ? Math.min(
        Date.parse(attempt.data?.deadline_at ?? ''),
        Date.parse(task.data.started_at) + task.data.time_limit_seconds * 1000,
      )
    : null
  const taskLeft = useCountdown(taskDeadline)

  useEffect(() => {
    if (attempt.data?.status === 'in_progress' && overallLeft === 0 && !expiredRef.current) {
      expiredRef.current = true
      void attempt.refetch()
    }
  }, [attempt, overallLeft])

  async function refreshOverview(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: assessmentStatusQueryKey }),
      queryClient.invalidateQueries({ queryKey: assessmentHistoryQueryKey }),
    ])
  }

  const answer = useMutation({
    mutationFn: (value: string[] | string | null) => submitAssessmentAnswer(attemptId, {
      attempt_task_id: task.data?.attempt_task_id ?? '',
      answer: value,
    }),
    onSuccess: async (response) => {
      queryClient.setQueryData(assessmentAttemptQueryKey(attemptId), response.attempt)
      if (response.finished) {
        queryClient.removeQueries({ queryKey: assessmentTaskQueryKey(attemptId) })
        await refreshOverview()
      } else {
        await queryClient.invalidateQueries({ queryKey: assessmentTaskQueryKey(attemptId) })
      }
    },
  })
  const finish = useMutation({
    mutationFn: () => finishAssessment(attemptId),
    onSuccess: async (response) => {
      queryClient.setQueryData(assessmentAttemptQueryKey(attemptId), response)
      queryClient.removeQueries({ queryKey: assessmentTaskQueryKey(attemptId) })
      setConfirmFinish(false)
      await refreshOverview()
    },
  })

  if (attempt.isPending) return <Card className="min-h-80"><CardContent className="grid min-h-80 place-items-center"><Spinner label="Загружаем попытку…" /></CardContent></Card>
  if (attempt.isError || !attempt.data) return <ErrorState error={attempt.error} onBack={() => void navigate({ to: '/assessments' })} />

  return (
    <section className="space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div><p className="text-sm font-semibold text-primary">Проверка знаний</p><h1 className="mt-1 break-words text-2xl font-semibold tracking-tight sm:text-3xl">{attempt.data.assessment.title}</h1></div>
        <Badge variant={attempt.data.status === 'in_progress' ? 'secondary' : attempt.data.result?.confirmed_grade ? 'success' : 'secondary'}>{attempt.data.status === 'in_progress' ? 'Идёт' : attempt.data.result?.confirmed_grade ? 'Грейд подтверждён' : 'Завершена'}</Badge>
      </div>

      {attempt.data.status !== 'in_progress' && attempt.data.result ? (
        <AssessmentResult attempt={attempt.data} />
      ) : (
        <>
          <Card>
            <CardContent className="space-y-3 p-4 sm:p-5">
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><span>Отвечено {attempt.data.answered_tasks} из {attempt.data.total_tasks}</span><span className="inline-flex items-center gap-2 font-semibold"><Clock3 className="size-4" aria-hidden="true" />На всю попытку: {clockLabel(overallLeft)}</span></div>
              <Progress value={attempt.data.total_tasks ? attempt.data.answered_tasks * 100 / attempt.data.total_tasks : 0} aria-label={`Отвечено ${attempt.data.answered_tasks} из ${attempt.data.total_tasks}`} />
            </CardContent>
          </Card>

          {task.isPending ? <Card className="min-h-80"><CardContent className="grid min-h-80 place-items-center"><Spinner label="Получаем задание…" /></CardContent></Card> : null}
          {task.isError ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Задание не загрузилось</AlertTitle><AlertDescription>{isApiError(task.error) ? task.error.message : 'Повторите попытку.'}</AlertDescription></Alert> : null}
          {task.data ? (
            <TaskQuestion
              key={task.data.attempt_task_id}
              task={task.data}
              secondsLeft={Math.min(taskLeft, overallLeft)}
              autoSubmitExpired={taskLeft === 0 && overallLeft > 0}
              pending={answer.isPending}
              error={answer.error}
              onSubmit={(value) => answer.mutate(value)}
            />
          ) : null}
          <div className="flex justify-end"><Button type="button" variant="outline" disabled={finish.isPending || answer.isPending} onClick={() => setConfirmFinish(true)}><Flag aria-hidden="true" />Завершить досрочно</Button></div>
        </>
      )}

      <AlertDialog open={confirmFinish} onOpenChange={setConfirmFinish}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Завершить проверку?</AlertDialogTitle><AlertDialogDescription>Неотвеченные задания получат 0 баллов. Вернуться к этой попытке после завершения нельзя.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Продолжить задания</AlertDialogCancel><AlertDialogAction onClick={() => finish.mutate()}>Завершить</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

function TaskQuestion({ task, secondsLeft, autoSubmitExpired, pending, error, onSubmit }: { task: TaskView; secondsLeft: number; autoSubmitExpired: boolean; pending: boolean; error: unknown; onSubmit: (answer: string[] | string | null) => void }) {
  const [single, setSingle] = useState('')
  const [multiple, setMultiple] = useState<string[]>([])
  const [text, setText] = useState('')
  const expiredSubmitted = useRef(false)
  const currentAnswer = task.kind === 'single_choice' ? single : task.kind === 'multiple_choice' ? multiple : text
  const valid = Array.isArray(currentAnswer) ? currentAnswer.length > 0 : currentAnswer.trim().length > 0

  useEffect(() => {
    if (autoSubmitExpired && !pending && !expiredSubmitted.current) {
      expiredSubmitted.current = true
      onSubmit(null)
    }
  }, [autoSubmitExpired, onSubmit, pending])

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3"><CardTitle>Задание {task.position} из {task.total}</CardTitle><span className="inline-flex items-center gap-2 text-sm font-semibold"><Clock3 className="size-4" aria-hidden="true" />{clockLabel(secondsLeft)}</span></div>
        {task.skills.length > 0 ? <CardDescription>Темы: {task.skills.join(', ')}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-5">
        {pending ? <Alert><Clock3 className="size-4 animate-spin" aria-hidden="true" /><AlertTitle>Решение проверяется</AlertTitle><AlertDescription>Дождитесь ответа перед следующим действием.</AlertDescription></Alert> : null}
        {error ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Ответ не отправлен</AlertTitle><AlertDescription className="space-y-3"><p>{isApiError(error) ? error.message : 'Повторите попытку.'}</p>{secondsLeft === 0 ? <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => onSubmit(null)}>Продолжить</Button> : null}</AlertDescription></Alert> : null}
        <p className="whitespace-pre-wrap text-base leading-7">{task.prompt}</p>
        {task.code ? <pre className="max-w-full overflow-x-auto rounded-lg bg-foreground p-4 text-sm leading-6 text-background"><code>{task.code}</code></pre> : null}

        {task.kind === 'single_choice' ? <fieldset className="space-y-2"><legend className="sr-only">Выберите один ответ</legend>{task.options.map((option) => <label key={option.id} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors hover:bg-muted/60 has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/40"><input className="sr-only" type="radio" name={`task-${task.attempt_task_id}`} value={option.id} checked={single === option.id} onChange={() => setSingle(option.id)} /><span className={`grid size-5 shrink-0 place-items-center rounded-full border ${single === option.id ? 'border-primary bg-primary text-primary-foreground' : 'border-input'}`}>{single === option.id ? <Check className="size-3" aria-hidden="true" /> : null}</span><span>{option.text}</span></label>)}</fieldset> : null}
        {task.kind === 'multiple_choice' ? <fieldset className="space-y-2"><legend className="sr-only">Выберите один или несколько ответов</legend>{task.options.map((option) => { const checked = multiple.includes(option.id); return <label key={option.id} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors hover:bg-muted/60"><Checkbox checked={checked} onCheckedChange={() => setMultiple(checked ? multiple.filter((id) => id !== option.id) : [...multiple, option.id])} />{option.text}</label> })}</fieldset> : null}
        {task.kind === 'text' ? <Textarea value={text} maxLength={1000} aria-label="Ответ" placeholder="Введите ответ" onChange={(event) => setText(event.target.value)} /> : null}

        <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-between"><Button type="button" variant="ghost" disabled={pending || secondsLeft === 0} onClick={() => onSubmit(null)}><SkipForward aria-hidden="true" />Пропустить</Button><Button type="button" disabled={pending || !valid || secondsLeft === 0} onClick={() => onSubmit(currentAnswer)}>{pending ? <Spinner label="Проверяем…" /> : 'Ответить'}</Button></div>
      </CardContent>
    </Card>
  )
}

function AssessmentResult({ attempt }: { attempt: AttemptResponse }) {
  const navigate = useNavigate()
  const result = attempt.result
  if (!result) return null
  const confirmed = Boolean(result.confirmed_grade)
  return (
    <div className="space-y-5">
      <Alert variant={confirmed ? 'success' : 'warning'}>{confirmed ? <BadgeCheck className="size-4" aria-hidden="true" /> : <CircleX className="size-4" aria-hidden="true" />}<AlertTitle>{confirmed ? `Подтверждённый грейд: ${gradeLabels[result.confirmed_grade ?? ''] ?? result.confirmed_grade}` : 'Грейд пока не подтверждён'}</AlertTitle><AlertDescription>{result.message}</AlertDescription></Alert>
      <Card><CardHeader><CardTitle>Результат</CardTitle><CardDescription>Все значения получены после завершения попытки.</CardDescription></CardHeader><CardContent className="space-y-5"><div className="grid gap-3 sm:grid-cols-3"><ResultValue label="Итог" value={`${result.percent}%`} /><ResultValue label="Баллы" value={`${result.score} из ${result.max_score}`} /><ResultValue label="Время" value={`${Math.ceil(result.duration_seconds / 60)} мин`} /></div>{result.skills.length > 0 ? <div><h2 className="text-sm font-semibold">Результаты по темам</h2><div className="mt-3 grid gap-2 sm:grid-cols-2">{result.skills.map((skill) => <div key={skill.skill} className="flex items-center justify-between gap-3 rounded-lg bg-muted px-3 py-2 text-sm"><span className="min-w-0 break-words">{skill.skill}</span><strong>{skill.percent}%</strong></div>)}</div></div> : null}<div className="flex justify-end border-t pt-5"><Button type="button" onClick={() => void navigate({ to: '/profile', search: { section: 'skills' } })}>Вернуться к навыкам</Button></div></CardContent></Card>
    </div>
  )
}

function ResultValue({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-muted px-3 py-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>
}

function ErrorState({ error, onBack }: { error: unknown; onBack: () => void }) {
  return <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Попытка не загрузилась</AlertTitle><AlertDescription className="space-y-3"><p>{isApiError(error) ? error.message : 'Повторите попытку.'}</p><Button type="button" size="sm" variant="outline" onClick={onBack}>К проверкам</Button></AlertDescription></Alert>
}
