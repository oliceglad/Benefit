import { Award, BadgeCheck, ChevronDown, ExternalLink, LockKeyhole, MapPin } from 'lucide-react'

import { candidateAchievements, candidateSkills, dateLabel, experienceLabel, publicAchievementUrl } from '@/features/talent/model/candidate-presentation'
import { formatLabels, gradeLabels, roleLabels } from '@/features/talent/model/talent-search'
import type { CandidateCard, WorkFormat } from '@/shared/api/generated/talent/models'
import { Badge } from '@/shared/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/ui/collapsible'

const achievementLevels: Record<string, string> = { international: 'Международный', federal: 'Федеральный', regional: 'Региональный', municipal: 'Муниципальный' }
const achievementResults: Record<string, string> = { winner: 'Победитель', prize: 'Призёр', participant: 'Участник' }
const searchStatuses: Record<string, string> = { active: 'Активно ищет работу', open: 'Рассматривает предложения', not_looking: 'Сейчас не ищет работу' }
const skillLevels: Record<string, string> = { beginner: 'Базовый', intermediate: 'Средний', advanced: 'Продвинутый', expert: 'Эксперт' }

export function TalentCandidateCard({ candidate, open, onOpenChange }: { candidate: CandidateCard; open: boolean; onOpenChange: (open: boolean) => void }) {
  const skills = candidateSkills(candidate.skills)
  const achievements = candidateAchievements(candidate.fsp_achievements)
  const confirmed = candidate.category.grade_status === 'confirmed'
  const name = candidate.full_name.trim() || 'Кандидат'
  const initials = name.split(/\s+/).slice(0, 2).map((word) => word.charAt(0)).join('')
  const category = [candidate.category.specialization ? roleLabels[candidate.category.specialization] : 'Специализация не указана', candidate.category.grade ? gradeLabels[candidate.category.grade] : 'Грейд не указан'].join(' · ')
  const salary = candidate.salary_from == null ? 'Ожидания не указаны' : `от ${new Intl.NumberFormat('ru-RU').format(candidate.salary_from)} ${candidate.salary_currency === 'RUB' ? '₽' : candidate.salary_currency ?? ''}`
  const lastActive = dateLabel(candidate.actuality.last_active_at)
  const triggerId = `candidate-${candidate.user_id}`
  const percent = candidate.category.verified_percent

  return (
    <Collapsible asChild open={open} onOpenChange={onOpenChange}>
      <article className={`overflow-hidden rounded-xl border bg-card shadow-card ${open ? 'border-primary/30' : ''}`}>
        <h2>
          <CollapsibleTrigger asChild>
            <button id={triggerId} type="button" className="flex w-full items-start gap-4 p-5 text-left outline-none transition-colors hover:bg-muted/40 focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/45" aria-label={`${open ? 'Свернуть' : 'Посмотреть'} карточку: ${name}`}>
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-primary/8 text-sm font-semibold text-primary" aria-hidden="true">{initials}</span>
              <span className="min-w-0 flex-1 space-y-2">
                <span className="flex flex-wrap items-start justify-between gap-2"><span className="block text-lg font-semibold tracking-tight">{name}</span><span className="text-sm font-medium">{salary}</span></span>
                <span className="block text-sm text-muted-foreground">{candidate.headline || category}</span>
                <span className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">{category}</Badge>
                  <Badge variant="secondary" className={confirmed ? 'bg-primary/8 text-primary' : ''}>{confirmed ? <BadgeCheck size={13} className="mr-1" aria-hidden="true" /> : null}{confirmed ? 'Грейд подтверждён' : 'Грейд не подтверждён'}</Badge>
                  {candidate.fsp_count > 0 ? <Badge className="gap-1 bg-primary/8 text-primary"><Award size={13} aria-hidden="true" />ФСП · {candidate.fsp_count}</Badge> : null}
                </span>
                <span className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"><span className="inline-flex items-center gap-1"><MapPin size={13} aria-hidden="true" />{candidate.city || 'Город не указан'}</span><span>{experienceLabel(candidate.experience_months)}</span><span>{searchStatuses[candidate.job_search_status] ?? 'Статус поиска не указан'}</span></span>
                {skills.length > 0 ? <span className="flex flex-wrap gap-1.5 pt-1">{skills.slice(0, 6).map((skill, index) => <Badge key={`${skill.name}-${index}`} variant="secondary" className="font-normal">{skill.name}</Badge>)}{skills.length > 6 ? <span className="self-center text-xs text-muted-foreground">ещё {skills.length - 6}</span> : null}</span> : null}
              </span>
              <ChevronDown className={`mt-1 size-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>
          </CollapsibleTrigger>
        </h2>
        <CollapsibleContent>
          <div role="region" aria-labelledby={triggerId} className="space-y-6 border-t p-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <section className="space-y-2"><h3 className="text-sm font-semibold">Категория и подтверждение</h3><p className="text-sm">{category}</p><p className="text-sm text-muted-foreground">{confirmed ? 'Подтверждено платформенным тестированием.' : 'Грейд указан в профиле и пока не подтверждён тестом.'}</p>{confirmed && candidate.category.test_title ? <p className="text-sm text-muted-foreground">Тест: {candidate.category.test_title}</p> : null}{confirmed && percent != null && percent >= 0 && percent <= 100 ? <p className="text-sm text-muted-foreground">Результат: {new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(percent)}%</p> : null}</section>
              <section className="space-y-2"><h3 className="text-sm font-semibold">Условия и активность</h3><p className="text-sm">{salary}</p><p className="text-sm text-muted-foreground">{candidate.work_formats.length ? candidate.work_formats.map((format) => formatLabels[format as WorkFormat] ?? format).join(' · ') : 'Формат работы не указан'}{candidate.relocation_ready ? ' · Готов к переезду' : ''}</p>{lastActive ? <p className="text-sm text-muted-foreground">Последняя активность: {lastActive}</p> : null}</section>
            </div>
            <section className="space-y-3"><h3 className="text-sm font-semibold">Навыки из профиля</h3>{skills.length ? <div className="flex flex-wrap gap-2">{skills.map((skill, index) => <Badge key={`${skill.name}-${index}`} variant="secondary" className="font-normal">{skill.name}{skill.level ? ` · ${skillLevels[skill.level] ?? skill.level}` : ''}{skill.years != null ? ` · ${skill.years} г.` : ''}</Badge>)}</div> : <p className="text-sm text-muted-foreground">Навыки не предоставлены.</p>}</section>
            <section className="space-y-3" aria-label={`Достижения ФСП: ${name}`}>
              <div className="flex flex-wrap items-center gap-2"><Award size={17} className="text-primary" aria-hidden="true" /><h3 className="text-sm font-semibold">Достижения ФСП</h3>{candidate.fsp_count > 0 ? <span className="text-xs text-muted-foreground">Подтверждённых: {candidate.fsp_count}</span> : null}</div>
              {achievements.length ? <ul className="grid gap-3 sm:grid-cols-2">{achievements.map((achievement, index) => {
                const url = publicAchievementUrl(achievement.url)
                const date = dateLabel(achievement.event_date)
                return <li key={index} className="space-y-2 rounded-lg border bg-muted/30 p-4"><p className="font-medium">{achievement.event || 'Мероприятие ФСП'}</p><div className="flex flex-wrap gap-2">{achievement.place != null ? <Badge className="bg-primary/8 text-primary">{achievement.place} место</Badge> : null}{achievement.result ? <Badge variant="secondary">{achievementResults[achievement.result] ?? achievement.result}</Badge> : null}{achievement.level ? <Badge variant="secondary">{achievementLevels[achievement.level] ?? achievement.level}</Badge> : null}</div>{achievement.discipline ? <p className="text-sm text-muted-foreground">{achievement.discipline}</p> : null}{achievement.team ? <p className="text-sm text-muted-foreground">Команда: {achievement.team}</p> : null}{date ? <p className="text-xs text-muted-foreground">{date}</p> : null}{url ? <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">Результаты мероприятия<ExternalLink size={13} aria-hidden="true" /></a> : null}</li>
              })}</ul> : <p className="rounded-lg bg-muted/50 p-4 text-sm leading-6 text-muted-foreground">{candidate.fsp_count > 0 ? 'Сервер сообщил о достижениях, но их подробности пока не предоставлены.' : 'Подтверждённых достижений ФСП в доступных данных нет. Кандидат может не иметь истории участия или скрыть её в настройках профиля.'}</p>}
            </section>
            <p className="flex items-start gap-2 border-t pt-4 text-xs leading-5 text-muted-foreground"><LockKeyhole size={15} className="mt-0.5 shrink-0" aria-hidden="true" />Контакты открываются после принятия приглашения или отклика кандидата.</p>
          </div>
        </CollapsibleContent>
      </article>
    </Collapsible>
  )
}
