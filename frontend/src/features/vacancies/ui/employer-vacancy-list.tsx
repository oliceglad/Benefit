import { Link } from '@tanstack/react-router'
import { ArrowUpRight, Globe, LockKeyhole, Pencil } from 'lucide-react'

import { employmentLabels, specializationLabels } from '@/features/vacancies/model/vacancy-form'
import { formatLabels, gradeLabels, salaryLabel, vacancyStatusLabels } from '@/features/vacancies/model/vacancy-search'
import type { VacancyResponse } from '@/shared/api/generated/employers/models'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'

export function EmployerVacancyList({ vacancies }: { vacancies: VacancyResponse[] }) {
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div className="hidden grid-cols-[minmax(0,1fr)_180px_160px] gap-5 border-b bg-muted/40 px-5 py-3 text-xs font-medium text-muted-foreground md:grid">
        <span>Вакансия и условия</span>
        <span>Публикация</span>
        <span className="text-right">Действия</span>
      </div>
      <div className="divide-y">
        {vacancies.map((vacancy) => (
          <article key={vacancy.id} className="grid min-w-0 items-center gap-5 p-5 transition-colors hover:bg-primary/[0.02] md:grid-cols-[minmax(0,1fr)_180px_160px]">
            <div className="min-w-0 space-y-3">
              <h2 className="text-base font-semibold">
                <Link to="/vacancies/$vacancyId" params={{ vacancyId: vacancy.id }} className="break-words rounded-sm outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring">
                  {vacancy.title}
                </Link>
              </h2>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span>{specializationLabels[vacancy.specialization]}</span>
                <span>{gradeLabels[vacancy.grade]}</span>
                {vacancy.work_format ? <span>{formatLabels[vacancy.work_format]}</span> : null}
                {vacancy.city ? <span>{vacancy.city}</span> : null}
                {vacancy.employment_type ? <span>{employmentLabels[vacancy.employment_type]}</span> : null}
              </div>
              <p className="text-sm font-medium">{salaryLabel(vacancy.salary_from, vacancy.salary_to, vacancy.currency)}</p>
            </div>
            <div className="space-y-2">
              <Badge variant="secondary" className={vacancy.status === 'published' ? 'bg-primary/10 text-primary' : vacancy.status === 'closed' ? 'bg-destructive/5 text-destructive' : ''}>{vacancyStatusLabels[vacancy.status]}</Badge>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {vacancy.status === 'published' ? <Globe className="size-3.5" aria-hidden="true" /> : <LockKeyhole className="size-3.5" aria-hidden="true" />}
                {vacancy.status === 'published' ? 'В каталоге' : 'Внутри компании'}
              </p>
              <p className="text-xs text-muted-foreground">Обновлена {new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(new Date(vacancy.updated_at))}</p>
            </div>
            <div className="flex flex-wrap gap-1 md:justify-end">
              <Button asChild variant="ghost" size="icon">
                <Link to="/vacancies/$vacancyId/edit" params={{ vacancyId: vacancy.id }} aria-label={`Редактировать ${vacancy.title}`}><Pencil aria-hidden="true" /></Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to="/vacancies/$vacancyId" params={{ vacancyId: vacancy.id }}>Открыть<ArrowUpRight aria-hidden="true" /></Link>
              </Button>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
