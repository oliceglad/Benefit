import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft, Building2, MapPin } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { applyForVacancy, getVacancy, myApplications } from '@/features/vacancies/api/vacancies'
import { formatLabels, gradeLabels, salaryLabel } from '@/features/vacancies/model/vacancy-search'
import { employmentLabels, specializationLabels } from '@/features/vacancies/model/vacancy-form'
import { VacancyActions } from '@/features/vacancies/ui/vacancy-actions'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

const applicationLabels = {
  new: 'Отклик отправлен',
  viewed: 'Отклик просмотрен',
  invited: 'Приглашение на собеседование',
  rejected: 'Отказ по отклику',
  withdrawn: 'Отклик отозван',
}

type VacancyDetailProps = { renderPipeline: (vacancyId: string) => ReactNode }

export function VacancyDetailPage({ renderPipeline }: VacancyDetailProps) {
  const { vacancyId } = useParams({ strict: false })
  return <VacancyDetail key={vacancyId} vacancyId={vacancyId!} renderPipeline={renderPipeline} />
}

function VacancyDetail({ vacancyId, renderPipeline }: { vacancyId: string } & VacancyDetailProps) {
  const employer = useSession().user?.role === 'employer'
  const queryClient = useQueryClient()
  const [letter, setLetter] = useState('')
  const vacancy = useQuery({
    queryKey: ['vacancies', 'detail', vacancyId, employer],
    queryFn: ({ signal }) => getVacancy(vacancyId, employer, signal),
  })
  const applications = useQuery({
    queryKey: ['applications', 'mine'],
    queryFn: ({ signal }) => myApplications(signal),
    enabled: !employer,
  })
  const apply = useMutation({
    mutationFn: () => applyForVacancy(vacancyId, letter),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['applications', 'mine'] })
    },
  })
  const previous = applications.data?.find((application) => (
    application.vacancy_id === vacancyId && ['new', 'viewed', 'invited'].includes(application.status)
  ))

  if (vacancy.isPending) return <Spinner label="Загружаем вакансию…" />
  if (vacancy.isError) return <RequestError error={vacancy.error} onRetry={() => { void vacancy.refetch() }} />
  const data = vacancy.data

  return (
    <section className="space-y-6">
      <Button asChild variant="ghost">
        <Link to="/vacancies" search={{ offset: 0 }}><ArrowLeft aria-hidden="true" />К вакансиям</Link>
      </Button>
      {employer ? <VacancyActions vacancy={data} /> : null}
      <div className="rounded-2xl border bg-card p-6 shadow-card sm:p-8">
        <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Building2 className="size-4" aria-hidden="true" />{data.company.name}
        </div>
        <h1 className="max-w-3xl text-3xl font-semibold leading-tight sm:text-4xl">{data.title}</h1>
        <p className="mt-5 text-2xl font-semibold">{salaryLabel(data.salary_from, data.salary_to, data.currency)}</p>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{gradeLabels[data.grade]}</Badge>
          <Badge variant="secondary">{specializationLabels[data.specialization]}</Badge>
          {data.work_format ? <Badge variant="secondary">{formatLabels[data.work_format]}</Badge> : null}
          {data.employment_type ? <Badge variant="secondary">{employmentLabels[data.employment_type]}</Badge> : null}
          {data.city ? (
            <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
              <MapPin className="size-4" aria-hidden="true" />{data.city}
            </span>
          ) : null}
        </div>
      </div>

      {renderPipeline(vacancyId)}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <article className="space-y-7 rounded-2xl border bg-card p-6 shadow-card sm:p-8">
          <div>
            <h2 className="mb-4 text-xl font-semibold">О работе</h2>
            <p className="whitespace-pre-wrap break-words text-sm leading-7 text-muted-foreground">{data.description}</p>
          </div>
          {data.skills?.length ? (
            <div>
              <h2 className="mb-3 text-lg font-semibold">Ключевые навыки</h2>
              <div className="flex flex-wrap gap-2">
                {data.skills.map((skill) => <Badge key={skill} variant="secondary">{skill}</Badge>)}
              </div>
            </div>
          ) : null}
        </article>

        <aside className="h-fit space-y-4 rounded-2xl border bg-card p-6 shadow-card">
          <h2 className="text-lg font-semibold">{employer ? 'Процесс подбора' : 'Отклик на вакансию'}</h2>
          {employer ? (
            <>
              <p className="text-sm leading-6 text-muted-foreground">Настройте этапы отбора под эту роль в конструкторе.</p>
              <Button asChild className="w-full"><Link to="/pipelines">Открыть пайплайны</Link></Button>
            </>
          ) : (
            <>
              {applications.isPending ? <Spinner label="Проверяем отклики…" /> : null}
              {applications.isError ? <RequestError error={applications.error} onRetry={() => { void applications.refetch() }} /> : null}
              {previous || apply.isSuccess ? (
                <p role="status" className="rounded-xl bg-success/10 p-3 text-sm text-success-foreground">
                  {previous ? applicationLabels[previous.status] : 'Отклик отправлен'}
                </p>
              ) : (
                <>
                  <Label htmlFor="cover-letter">Сопроводительное письмо</Label>
                  <Textarea
                    id="cover-letter"
                    maxLength={4000}
                    rows={5}
                    placeholder="Расскажите, почему вам интересна эта роль"
                    value={letter}
                    onChange={(event) => setLetter(event.target.value)}
                    disabled={apply.isPending}
                  />
                  <p className="text-xs leading-5 text-muted-foreground">
                    Необязательно. Отклик откроет работодателю контакты из вашего профиля.
                  </p>
                  <Button className="w-full" disabled={apply.isPending || !applications.isSuccess} onClick={() => apply.mutate()}>
                    {apply.isPending ? <Spinner label="Отправляем…" /> : 'Откликнуться'}
                  </Button>
                </>
              )}
              {apply.isError ? <RequestError error={apply.error} /> : null}
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
