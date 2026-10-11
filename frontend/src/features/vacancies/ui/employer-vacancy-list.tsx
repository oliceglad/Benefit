import { Link } from '@tanstack/react-router'
import { MoreHorizontal, Pencil } from 'lucide-react'

import { employmentLabels, specializationLabels } from '@/features/vacancies/model/vacancy-form'
import { formatLabels, gradeLabels, salaryLabel, vacancyStatusLabels } from '@/features/vacancies/model/vacancy-search'
import type { VacancyResponse } from '@/shared/api/generated/employers/models'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/shared/ui/dropdown-menu'

function updatedAt(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value))
}

function VacancyMenu({ vacancy }: { vacancy: VacancyResponse }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="icon" aria-label={`Действия с вакансией «${vacancy.title}»`}><MoreHorizontal aria-hidden="true" /></Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link to="/vacancies/$vacancyId/edit" params={{ vacancyId: vacancy.id }}><Pencil aria-hidden="true" />Редактировать</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function VacancyMeta({ vacancy }: { vacancy: VacancyResponse }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
      <span>{specializationLabels[vacancy.specialization]}</span>
      <span>{gradeLabels[vacancy.grade]}</span>
      {vacancy.work_format ? <span>{formatLabels[vacancy.work_format]}</span> : null}
      {vacancy.city ? <span>{vacancy.city}</span> : null}
      {vacancy.employment_type ? <span>{employmentLabels[vacancy.employment_type]}</span> : null}
    </div>
  )
}

export function EmployerVacancyList({ vacancies }: { vacancies: VacancyResponse[] }) {
  return (
    <>
      <div className="hidden md:block">
        <div role="row" className="grid grid-cols-[minmax(0,1fr)_180px_150px_52px] gap-5 border-y bg-muted/35 px-5 py-3 text-xs font-medium text-muted-foreground">
          <span>Вакансия</span><span>Зарплата</span><span>Статус</span><span className="sr-only">Действия</span>
        </div>
        <div className="divide-y">
          {vacancies.map((vacancy) => (
            <article key={vacancy.id} className="grid min-w-0 grid-cols-[minmax(0,1fr)_180px_150px_52px] items-center gap-5 px-5 py-4 transition-colors hover:bg-primary/[0.025]">
              <div className="min-w-0 space-y-2">
                <h2 className="text-sm font-semibold leading-5"><Link to="/vacancies/$vacancyId" params={{ vacancyId: vacancy.id }} className="break-words rounded-sm underline-offset-4 hover:text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring">{vacancy.title}</Link></h2>
                <VacancyMeta vacancy={vacancy} />
              </div>
              <p className="text-sm font-medium">{salaryLabel(vacancy.salary_from, vacancy.salary_to, vacancy.currency)}</p>
              <div className="space-y-1.5"><Badge variant={vacancy.status === 'published' ? 'success' : 'secondary'}>{vacancyStatusLabels[vacancy.status]}</Badge><p className="text-xs text-muted-foreground">{updatedAt(vacancy.updated_at)}</p></div>
              <VacancyMenu vacancy={vacancy} />
            </article>
          ))}
        </div>
      </div>

      <div className="divide-y md:hidden">
        {vacancies.map((vacancy) => (
          <article key={vacancy.id} className="min-w-0 space-y-3 p-4">
            <div className="flex min-w-0 items-start gap-3"><h2 className="min-w-0 flex-1 text-base font-semibold leading-6"><Link to="/vacancies/$vacancyId" params={{ vacancyId: vacancy.id }} className="break-words underline-offset-4 hover:text-primary hover:underline">{vacancy.title}</Link></h2><VacancyMenu vacancy={vacancy} /></div>
            <VacancyMeta vacancy={vacancy} />
            <p className="text-sm font-medium">{salaryLabel(vacancy.salary_from, vacancy.salary_to, vacancy.currency)}</p>
            <div className="flex flex-wrap items-center justify-between gap-2"><Badge variant={vacancy.status === 'published' ? 'success' : 'secondary'}>{vacancyStatusLabels[vacancy.status]}</Badge><time className="text-xs text-muted-foreground" dateTime={vacancy.updated_at}>Обновлена {updatedAt(vacancy.updated_at)}</time></div>
          </article>
        ))}
      </div>
    </>
  )
}
