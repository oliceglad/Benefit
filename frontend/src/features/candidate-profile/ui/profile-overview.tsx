import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import {
  buildProfileOverviewSummary,
  type ProfileOverviewSummary,
} from '@/features/candidate-profile/model/profile-overview-summary'
import {
  isProfileSectionId,
  nextStepTitle,
  type ProfileSectionId,
} from '@/features/candidate-profile/model/profile-sections'
import { PhotoManager } from '@/features/candidate-profile/ui/photo-manager'
import type { ConsentStatus, ProfileResponse } from '@/shared/api/generated/candidates/models'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Progress } from '@/shared/ui/progress'

const profileRows: ReadonlyArray<{ id: ProfileSectionId; title: string }> = [
  { id: 'personal', title: 'Личные данные' },
  { id: 'contacts', title: 'Контакты' },
  { id: 'specialization', title: 'Специализация' },
  { id: 'skills', title: 'Навыки и языки' },
  { id: 'experience', title: 'Опыт и образование' },
  { id: 'preferences', title: 'Пожелания к работе' },
]

export function CandidateProfileOverview({
  profile,
  dictionaries,
  consents,
  consentsFailed,
  resumeActions,
  onNavigate,
}: {
  profile: ProfileResponse
  dictionaries: ProfileDictionaries
  consents?: ConsentStatus[]
  consentsFailed: boolean
  resumeActions: ReactNode
  onNavigate: (section: ProfileSectionId) => void
}) {
  const summary = buildProfileOverviewSummary(profile, dictionaries, consents, consentsFailed)

  return (
    <div className="space-y-6">
      <ProfileSummaryCard profile={profile} onNavigate={onNavigate} />

      <OverviewGroup title="Данные профиля" rows={profileRows} summary={summary} onNavigate={onNavigate} />
      <OverviewGroup title="Видимость профиля" rows={[{ id: 'consents', title: 'Согласия и публикация' }]} summary={summary} onNavigate={onNavigate} />

      <section aria-labelledby="resume-actions-title" className="rounded-2xl border bg-card p-4 sm:p-5">
        <div className="mb-3">
          <h2 id="resume-actions-title" className="font-semibold">Резюме</h2>
          <p className="mt-1 text-sm text-muted-foreground">Импортируйте данные или скачайте сохранённую версию.</p>
        </div>
        {resumeActions}
      </section>
    </div>
  )
}

export function ProfileSummaryCard({ profile, onNavigate }: { profile: ProfileResponse; onNavigate: (section: ProfileSectionId) => void }) {
  const name = [profile.first_name, profile.last_name].filter(Boolean).join(' ')
  const nextTitle = nextStepTitle(profile.completeness)
  const nextSection = isProfileSectionId(profile.completeness.next_step) ? profile.completeness.next_step : null
  return (
    <Card className="shadow-none">
      <CardContent className="space-y-4 p-4 sm:p-5">
        <div className="flex min-w-0 items-start gap-4">
          <PhotoManager profile={profile} />
          <div className="min-w-0 flex-1 pt-0.5">
            <h1 className="min-w-0 break-words text-xl font-semibold tracking-tight sm:text-2xl">{name || 'Мой профиль'}</h1>
            {profile.headline ? <p className="mt-1 break-words text-sm leading-5 text-muted-foreground">{profile.headline}</p> : null}
            <Badge className="mt-2" variant={profile.status === 'published' ? 'success' : 'secondary'}>{profile.status === 'published' ? 'Опубликован' : 'Черновик'}</Badge>
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between gap-3 text-xs"><span className="text-muted-foreground">Профиль заполнен</span><strong>{profile.completeness.percent}%</strong></div>
              <Progress value={profile.completeness.percent} aria-label={`Профиль заполнен на ${profile.completeness.percent}%`} />
            </div>
          </div>
        </div>
        {nextTitle && nextSection ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="min-h-11 w-full justify-between px-0 py-2 text-left font-medium hover:bg-transparent hover:text-primary lg:w-fit lg:justify-center lg:gap-2 lg:border lg:border-border lg:bg-secondary lg:px-4 lg:hover:bg-accent"
            onClick={() => onNavigate(nextSection)}
          >
            <span className="min-w-0 whitespace-normal break-words"><span className="text-muted-foreground">Далее:</span> {lowercaseFirst(nextTitle)}</span>
            <ChevronRight className="shrink-0" aria-hidden="true" />
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

function OverviewGroup({
  title,
  rows,
  summary,
  onNavigate,
}: {
  title: string
  rows: ReadonlyArray<{ id: ProfileSectionId; title: string }>
  summary: ProfileOverviewSummary
  onNavigate: (section: ProfileSectionId) => void
}) {
  return (
    <section aria-labelledby={`overview-${rows[0]?.id}`}>
      <h2 id={`overview-${rows[0]?.id}`} className="mb-2 px-1 text-sm font-semibold text-muted-foreground">{title}</h2>
      <div className="overflow-hidden rounded-2xl border bg-card">
        {rows.map((row) => (
          <button key={row.id} type="button" className="relative flex w-full min-w-0 items-center gap-3 px-4 py-3.5 text-left outline-none transition-colors after:absolute after:bottom-0 after:left-4 after:right-0 after:h-px after:bg-border last:after:hidden hover:bg-muted/45 focus-visible:bg-muted focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/45" onClick={() => onNavigate(row.id)}>
            <span className="min-w-0 flex-1">
              <span className="block font-medium">{row.title}</span>
              <span className="mt-0.5 line-clamp-2 break-words text-sm leading-5 text-muted-foreground">{summary[row.id]}</span>
            </span>
            <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  )
}

function lowercaseFirst(value: string): string {
  return `${value.charAt(0).toLocaleLowerCase('ru-RU')}${value.slice(1)}`
}
