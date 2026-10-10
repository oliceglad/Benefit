import { Link } from '@tanstack/react-router'
import { ArrowUpRight, Building2, MapPin } from 'lucide-react'

import { formatLabels, gradeLabels, salaryLabel, vacancyStatusLabels } from '@/features/vacancies/model/vacancy-search'
import type { VacancyResponse } from '@/shared/api/generated/employers/models'
import { Badge } from '@/shared/ui/badge'

export function VacancyCard({ vacancy, employer = false }: { vacancy: VacancyResponse; employer?: boolean }) {
  return (
    <article className="group flex min-w-0 flex-col gap-5 rounded-2xl border bg-card p-6 shadow-card transition-colors hover:border-primary/35">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
          <Building2 className="size-4 shrink-0" aria-hidden="true" />
          <span className="truncate">{vacancy.company.name}</span>
        </div>
        {employer ? (
          <Badge variant={vacancy.status === 'published' ? 'success' : 'secondary'}>{vacancyStatusLabels[vacancy.status]}</Badge>
        ) : null}
      </div>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold leading-snug">
          <Link
            to="/vacancies/$vacancyId"
            params={{ vacancyId: vacancy.id }}
            className="rounded-sm outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
          >
            {vacancy.title}
          </Link>
        </h2>
        <p className="text-lg font-semibold">{salaryLabel(vacancy.salary_from, vacancy.salary_to, vacancy.currency)}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">{gradeLabels[vacancy.grade]}</Badge>
        {vacancy.work_format ? <Badge variant="secondary">{formatLabels[vacancy.work_format]}</Badge> : null}
        {vacancy.city ? (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="size-3.5" aria-hidden="true" />{vacancy.city}
          </span>
        ) : null}
      </div>
      <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">{vacancy.description}</p>
      <div className="mt-auto flex flex-wrap gap-1.5">
        {vacancy.skills?.slice(0, 5).map((skill) => (
          <span key={skill} className="rounded-md border px-2 py-1 text-xs text-muted-foreground">{skill}</span>
        ))}
      </div>
      <Link
        to="/vacancies/$vacancyId"
        params={{ vacancyId: vacancy.id }}
        className="inline-flex min-h-10 items-center justify-between gap-2 rounded-lg text-sm font-semibold text-primary outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Подробнее о вакансии<ArrowUpRight className="size-4" aria-hidden="true" />
      </Link>
    </article>
  )
}
