import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { getNeed, listNeeds, needKey, needsKey } from '@/features/talent/api/needs'
import { talentSearchSchema } from '@/features/talent/model/talent-search'
import { NeedEditor } from '@/features/talent/ui/need-editor'
import { NeedMatching } from '@/features/talent/ui/need-matching'
import { TalentCatalog } from '@/features/talent/ui/talent-catalog'
import type { NeedResponse } from '@/shared/api/generated/employers/models'
import type { CandidateCard } from '@/shared/api/generated/talent/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'

export function TalentPage({ prepareNewNeed, candidateActions }: { prepareNewNeed: (form: ReactNode, onCancel: () => void) => ReactNode; candidateActions?: (candidate: CandidateCard, need?: NeedResponse) => ReactNode }) {
  const search = talentSearchSchema.parse(useSearch({ strict: false }))
  const navigate = useNavigate()
  const userId = useSession().user?.id
  const [editor, setEditor] = useState<{ mode: 'new' | 'edit'; needId?: string } | null>(null)
  const editorMode = editor?.needId === search.need ? editor?.mode : undefined
  const needs = useQuery({ queryKey: needsKey(userId), queryFn: ({ signal }) => listNeeds(signal) })
  const selected = useQuery({ queryKey: needKey(userId, search.need), queryFn: ({ signal }) => getNeed(search.need!, signal), enabled: Boolean(search.need) })
  const firstNeed = needs.data?.find((need) => need.status === 'active') ?? needs.data?.[0]
  function saved(need: NeedResponse) {
    setEditor(null)
    void navigate({ to: '/talent', search: { ...search, need: need.id, offset: 0, candidate: undefined }, ignoreBlocker: true, resetScroll: true })
  }
  const form = <NeedEditor key={editorMode === 'edit' ? selected.data?.id : 'new'} need={editorMode === 'edit' ? selected.data : undefined} onSaved={saved} onCancel={() => setEditor(null)} />

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4"><div className="max-w-2xl space-y-2"><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Подбор кандидатов</h1><p className="text-sm leading-6 text-muted-foreground">Найдите специалиста по подтверждённой квалификации или сохраните требования команды для персональной подборки.</p></div><Button disabled={Boolean(editorMode)} onClick={() => setEditor({ mode: 'new', needId: search.need })}><Plus size={16} aria-hidden="true" />Новая потребность</Button></header>
      <section aria-label="Выбор потребности" className="space-y-4 rounded-xl border bg-card p-4 shadow-card sm:p-5">
        <nav aria-label="Способ подбора" className="flex flex-wrap gap-2 border-b pb-4">
          <Button variant={!search.need && !editorMode ? 'outline' : 'ghost'} aria-pressed={!search.need && !editorMode} disabled={Boolean(editorMode)} onClick={() => { void navigate({ to: '/talent', search: { ...search, need: undefined, offset: 0, candidate: undefined }, resetScroll: false }) }}>Весь банк</Button>
          <Button variant={search.need || editorMode ? 'outline' : 'ghost'} aria-pressed={Boolean(search.need || editorMode)} disabled={Boolean(editorMode) || needs.isPending || needs.isError} onClick={() => { if (firstNeed) { void navigate({ to: '/talent', search: { ...search, need: firstNeed.id, offset: 0, candidate: undefined }, resetScroll: false }) } else setEditor({ mode: 'new', needId: search.need }) }}>По потребности команды</Button>
        </nav>
        <div className="flex flex-wrap items-end gap-4"><div className="min-w-0 flex-1 space-y-2"><Label htmlFor="talent-need">Сохранённая потребность</Label><select id="talent-need" className="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40" value={search.need ?? ''} disabled={Boolean(editorMode)} onChange={(event) => { void navigate({ to: '/talent', search: { ...search, need: event.target.value || undefined, offset: 0, candidate: undefined }, resetScroll: false }) }}>
          <option value="">Не выбрана · поиск по всему банку</option>
          {search.need && !needs.data?.some((need) => need.id === search.need) ? <option value={search.need}>{selected.data?.title ?? 'Загружаем потребность…'}</option> : null}
          {needs.data?.map((need) => <option key={need.id} value={need.id}>{need.title}{need.status === 'closed' ? ' · закрыта' : ''}</option>)}
        </select></div><p className="max-w-sm text-xs leading-5 text-muted-foreground">{search.need ? 'Подборка учитывает сохранённые требования. Фильтры банка сохранятся при возвращении.' : 'Фильтры банка применяются вручную. Подбор по потребности учитывает требования команды и объясняет соответствие.'}</p></div>
        {needs.isPending ? <p className="w-full text-xs text-muted-foreground">Загружаем ваши потребности…</p> : null}
        {needs.isError ? <div className="w-full"><RequestError error={needs.error} onRetry={() => { void needs.refetch() }} /></div> : null}
        {needs.data?.length === 0 && !editorMode ? <p className="w-full text-xs leading-5 text-muted-foreground">Сохраните требования команды — сравним профили по навыкам, грейду, опыту и достижениям ФСП.</p> : null}
      </section>
      {editorMode === 'new' ? prepareNewNeed(form, () => setEditor(null)) : search.need && selected.isPending ? <Spinner label="Загружаем условия подбора…" /> : search.need && selected.isError ? <RequestError error={selected.error} onRetry={() => { void selected.refetch() }} /> : editorMode === 'edit' && selected.data ? form : search.need && selected.data ? <NeedMatching need={selected.data} candidateActions={candidateActions} onEdit={() => setEditor({ mode: 'edit', needId: search.need })} /> : <TalentCatalog candidateActions={candidateActions} />}
    </section>
  )
}
