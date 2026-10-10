import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearch } from '@tanstack/react-router'
import { Award, ExternalLink, Link2, RefreshCw } from 'lucide-react'

import { fspProviders, linkFsp, syncFsp } from '@/features/candidate-profile/api/fsp'
import { candidateProfileQueryKey } from '@/features/candidate-profile/api/profile'
import type { FspInfo } from '@/shared/api/generated/candidates/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { isApiError } from '@/shared/api/transport/api-error'
import { useSession } from '@/shared/session/session'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

const levels: Record<string, string> = { international: 'Международный', federal: 'Федеральный', regional: 'Региональный', municipal: 'Муниципальный' }
const results: Record<string, string> = { winner: 'Победитель', prize: 'Призёр', participant: 'Участник' }
function safeUrl(value: string | null) {
  try { const url = new URL(value ?? ''); return ['https:', 'http:'].includes(url.protocol) ? url.href : null } catch { return null }
}

export function FspPanel({ fsp, disabled }: { fsp: FspInfo; disabled: boolean }) {
  const userId = useSession().user?.id
  const search = useSearch({ strict: false })
  const client = useQueryClient()
  const providers = useQuery({ queryKey: ['fsp-providers', userId], queryFn: ({ signal }) => fspProviders(signal) })
  const link = useMutation({ mutationFn: linkFsp, onSuccess: (url) => window.location.assign(url) })
  const sync = useMutation({ mutationFn: syncFsp, onSuccess: (profile) => {
    client.setQueryData(candidateProfileQueryKey, profile)
    void client.invalidateQueries({ queryKey: ['talent'] })
    void client.invalidateQueries({ queryKey: ['talent-matches'] })
  }, onError: () => { void client.invalidateQueries({ queryKey: candidateProfileQueryKey }) } })
  const pending = link.isPending || sync.isPending
  const enabled = providers.data?.some((provider) => provider.id === 'fsp_id')
  return <section aria-label="Профиль и достижения ФСП" className="space-y-4 rounded-xl border bg-card p-5">
    <div className="flex flex-wrap items-center gap-3"><Award className="size-5 text-primary" aria-hidden="true" /><h3 className="font-semibold">Достижения ФСП</h3><Badge variant="secondary">{fsp.linked ? 'ФСП ID связан' : 'ФСП ID не связан'}</Badge></div>
    <p className="text-sm leading-6 text-muted-foreground">Свяжите свой ФСП ID, чтобы работодатели увидели подтверждённые результаты соревнований. Их видимость регулируется настройкой «Показывать достижения ФСП» выше.</p>
    {fsp.participant_id ? <p className="text-xs text-muted-foreground">Идентификатор участника: {fsp.participant_id}</p> : null}
    {fsp.synced_at ? <p className="text-xs text-muted-foreground">Обновлено: {new Date(fsp.synced_at).toLocaleString('ru-RU')}</p> : null}
    {search.linked === 'fsp_id' ? <p role="status" className="text-sm text-primary">Вы вернулись после входа в ФСП. Проверьте связь и обновите достижения.</p> : null}
    {providers.isPending ? <Spinner label="Проверяем доступность ФСП ID…" /> : null}
    {providers.isError ? <RequestError error={providers.error} onRetry={() => { void providers.refetch() }} /> : null}
    {providers.isSuccess && !enabled && !fsp.linked ? <p className="rounded-lg bg-muted/50 p-3 text-sm leading-6 text-muted-foreground">Вход через ФСП ID пока не включён на сервере. Профилем можно пользоваться без привязки. Если аккаунт был связан раньше, проверьте связь кнопкой ниже.</p> : null}
    <div className="flex flex-wrap gap-2">{!fsp.linked && enabled ? <Button type="button" variant="outline" disabled={disabled || pending} onClick={() => link.mutate()}><Link2 size={16} aria-hidden="true" />Привязать ФСП ID</Button> : null}<Button type="button" variant="outline" disabled={disabled || pending} onClick={() => sync.mutate()}>{sync.isPending ? <Spinner label="Обновляем…" /> : <RefreshCw size={16} aria-hidden="true" />}{fsp.linked ? 'Обновить достижения' : 'Проверить связь и обновить'}</Button></div>
    {disabled ? <p className="text-xs text-muted-foreground">Сначала сохраните изменения текущего шага.</p> : null}
    {link.isError ? <RequestError error={link.error} /> : null}{sync.isError ? isApiError(sync.error) && sync.error.code === 'fsp_not_linked' ? <p role="alert" className="rounded-lg border bg-muted/40 p-3 text-sm">ФСП ID ещё не привязан. Сначала свяжите аккаунт, затем обновите достижения.</p> : <RequestError error={sync.error} /> : null}{sync.isSuccess ? <p role="status" className="text-sm text-primary">Связь проверена. Получено достижений: {sync.data.fsp.achievements.length}.</p> : null}
    {fsp.achievements.length ? <ul className="grid gap-3 sm:grid-cols-2">{fsp.achievements.map((achievement) => {
      const url = safeUrl(achievement.url)
      return <li key={achievement.external_id} className="space-y-2 rounded-lg border p-4"><p className="text-sm font-semibold">{achievement.event}</p><div className="flex flex-wrap gap-2">{achievement.place != null ? <Badge variant="secondary">{achievement.place} место</Badge> : null}{achievement.result ? <Badge variant="secondary">{results[achievement.result] ?? achievement.result}</Badge> : null}{achievement.level ? <Badge variant="secondary">{levels[achievement.level] ?? achievement.level}</Badge> : null}</div>{achievement.discipline ? <p className="text-sm text-muted-foreground">{achievement.discipline}</p> : null}{achievement.team ? <p className="text-sm text-muted-foreground">Команда: {achievement.team}</p> : null}{achievement.event_date ? <p className="text-xs text-muted-foreground">{new Date(achievement.event_date).toLocaleDateString('ru-RU')}</p> : null}{url ? <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-primary underline underline-offset-4">Результаты мероприятия<ExternalLink size={13} aria-hidden="true" /></a> : null}</li>
    })}</ul> : <p className="text-sm leading-6 text-muted-foreground">{fsp.linked ? 'История соревнований пока пуста. Обновите достижения позже.' : 'После привязки и синхронизации здесь появится история соревнований.'} Подтверждённые данные загружаются с сервера и не редактируются вручную.</p>}
  </section>
}
