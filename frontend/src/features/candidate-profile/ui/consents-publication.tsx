import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, FileWarning, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import {
  candidateConsentsQueryKey,
  candidateProfileQueryKey,
  getCandidateConsents,
  grantCandidateConsent,
  publishCandidateProfile,
  revokeCandidateConsent,
  unpublishCandidateProfile,
} from '@/features/candidate-profile/api/profile'
import { resolveDocumentUrl } from '@/features/candidate-profile/model/legal-document-url'
import { missingFieldLabel, type ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import type { ConsentStatus, ConsentType, ProfileResponse } from '@/shared/api/generated/candidates/models'
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
import { Checkbox } from '@/shared/ui/checkbox'
import { Spinner } from '@/shared/ui/spinner'

type ConfirmAction = { kind: 'revoke'; consent: ConsentStatus } | { kind: 'publish' } | { kind: 'unpublish' } | null

const missingFieldSection: Record<string, ProfileSectionId> = {
  last_name: 'personal',
  first_name: 'personal',
  contacts: 'contacts',
  headline: 'specialization',
  grade: 'specialization',
  roles: 'specialization',
  skills: 'skills',
  experience_or_projects: 'experience',
  consents: 'consents',
}

export function ConsentsPublication({
  profile,
  onNavigate,
  standalone = false,
}: {
  profile: ProfileResponse
  onNavigate: (section: ProfileSectionId) => void
  standalone?: boolean
}) {
  const queryClient = useQueryClient()
  const consents = useQuery({ queryKey: candidateConsentsQueryKey, queryFn: ({ signal }) => getCandidateConsents(signal) })
  const [accepted, setAccepted] = useState<Partial<Record<ConsentType, boolean>>>({})
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null)

  async function refreshProfile(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: candidateProfileQueryKey })
  }

  const grant = useMutation({
    mutationFn: grantCandidateConsent,
    onSuccess: async (data, variables) => {
      queryClient.setQueryData(candidateConsentsQueryKey, data)
      setAccepted((current) => ({ ...current, [variables.type]: false }))
      await refreshProfile()
    },
  })
  const revoke = useMutation({
    mutationFn: revokeCandidateConsent,
    onSuccess: async (data) => {
      queryClient.setQueryData(candidateConsentsQueryKey, data)
      await refreshProfile()
    },
  })
  const publish = useMutation({
    mutationFn: publishCandidateProfile,
    onSuccess: async (data) => {
      queryClient.setQueryData(candidateProfileQueryKey, data)
      await refreshProfile()
    },
  })
  const unpublish = useMutation({
    mutationFn: unpublishCandidateProfile,
    onSuccess: async (data) => {
      queryClient.setQueryData(candidateProfileQueryKey, data)
      await refreshProfile()
    },
  })

  const pending = grant.isPending || revoke.isPending || publish.isPending || unpublish.isPending
  const actionError = grant.error ?? revoke.error ?? publish.error ?? unpublish.error

  function confirm(): void {
    const action = confirmAction
    setConfirmAction(null)
    if (!action) return
    if (action.kind === 'revoke') revoke.mutate(action.consent.type)
    if (action.kind === 'publish') publish.mutate()
    if (action.kind === 'unpublish') unpublish.mutate()
  }

  return (
    <div className={standalone ? 'space-y-6' : 'space-y-6 rounded-2xl border bg-card p-6 shadow-card'}>
      <section aria-labelledby="consents-title" className="space-y-4">
        <div>
          <h2 id="consents-title" className="text-lg font-semibold">Согласия</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">Каждое согласие принимается отдельно после ознакомления с действующей версией документа.</p>
        </div>
          {consents.isLoading ? <Spinner label="Загружаем документы…" /> : null}
          {consents.isError ? <ErrorAlert error={consents.error} title="Не удалось загрузить согласия" /> : null}
          {consents.data?.map((consent) => {
            const url = resolveDocumentUrl(consent.document_url)
            return (
              <article key={consent.type} className="space-y-4 rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{consent.title}</h3>
                    <p className="mt-1 text-xs text-muted-foreground">Версия {consent.required_version}</p>
                  </div>
                  <Badge variant={consent.granted ? 'success' : 'secondary'}>{consent.granted ? 'Принято' : 'Не принято'}</Badge>
                </div>
                {url ? (
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div className="space-y-3">
                      <a className="inline-flex items-center gap-2 text-sm font-medium text-primary underline-offset-4 hover:underline" href={url} target="_blank" rel="noreferrer">
                        Открыть документ <ExternalLink className="size-4" aria-hidden="true" />
                      </a>
                      {!consent.granted ? (
                        <label className="flex min-h-11 cursor-pointer items-start gap-3 py-2 text-sm transition-colors hover:text-primary">
                          <Checkbox className="mt-0.5" disabled={pending} checked={accepted[consent.type] ?? false} onCheckedChange={(checked) => setAccepted((current) => ({ ...current, [consent.type]: checked === true }))} />
                          <span>Я ознакомился с документом и принимаю его условия</span>
                        </label>
                      ) : null}
                    </div>
                    {consent.granted ? (
                      <Button className="self-end" type="button" variant="outline" disabled={pending} onClick={() => setConfirmAction({ kind: 'revoke', consent })}>Отозвать согласие</Button>
                    ) : (
                      <Button className="self-end" type="button" disabled={!accepted[consent.type] || pending} onClick={() => grant.mutate({ type: consent.type, version: consent.required_version })}>Принять согласие</Button>
                    )}
                  </div>
                ) : (
                  <p className="flex items-start gap-2 text-sm leading-5 text-warning-foreground" role="status"><FileWarning className="mt-0.5 size-4 shrink-0" aria-hidden="true" />Ссылка на действующий документ недоступна. Принять согласие пока нельзя.</p>
                )}
              </article>
            )
          })}
      </section>

      <section aria-labelledby="publication-title" className="space-y-5 border-t pt-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="publication-title" className="text-lg font-semibold">Публикация профиля</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">Заполнение на 100% и публикация — разные состояния.</p>
            </div>
            <Badge variant={profile.status === 'published' ? 'success' : 'secondary'}>{profile.status === 'published' ? 'Опубликован' : 'Черновик'}</Badge>
          </div>
          {actionError ? <ErrorAlert error={actionError} title="Действие не выполнено" /> : null}
          {!profile.completeness.can_publish ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">Перед публикацией заполните:</p>
              <ul className="space-y-2">
                {profile.completeness.missing_required.map((field) => (
                  <li key={field} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted px-3 py-2 text-sm">
                    <span>{missingFieldLabel(field)}</span>
                    {missingFieldSection[field] && missingFieldSection[field] !== 'consents' ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => onNavigate(missingFieldSection[field])}>Перейти</Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <Alert variant="success">
              <ShieldCheck className="size-4" aria-hidden="true" />
              <AlertTitle>Профиль готов к публикации</AlertTitle>
              <AlertDescription>Все обязательные данные заполнены.</AlertDescription>
            </Alert>
          )}
          {profile.status === 'published' ? (
            <Button type="button" variant="outline" disabled={pending} onClick={() => setConfirmAction({ kind: 'unpublish' })}>{unpublish.isPending ? <Spinner label="Снимаем с публикации…" /> : 'Снять с публикации'}</Button>
          ) : (
            <Button type="button" disabled={!profile.completeness.can_publish || pending} onClick={() => setConfirmAction({ kind: 'publish' })}>{publish.isPending ? <Spinner label="Публикуем…" /> : 'Опубликовать профиль'}</Button>
          )}
          <p className="text-xs leading-5 text-muted-foreground">Появление профиля в поиске работодателей может занять время.</p>
      </section>

      <AlertDialog open={confirmAction !== null} onOpenChange={(open) => { if (!open) setConfirmAction(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmAction?.kind === 'revoke' ? 'Отозвать согласие?' : confirmAction?.kind === 'publish' ? 'Опубликовать профиль?' : 'Снять профиль с публикации?'}</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmAction?.kind === 'revoke' ? 'Отзыв согласия может автоматически снять профиль с публикации.' : confirmAction?.kind === 'publish' ? 'Работодатели смогут увидеть разрешённые данные профиля. Контакты открываются только по правилам сервиса.' : 'Профиль перестанет быть опубликован. Сохранённые данные останутся в черновике.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={confirm}>{confirmAction?.kind === 'publish' ? 'Опубликовать' : 'Подтвердить'}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function ErrorAlert({ error, title }: { error: unknown; title: string }) {
  return <Alert variant="destructive"><FileWarning className="size-4" aria-hidden="true" /><AlertTitle>{title}</AlertTitle><AlertDescription>{isApiError(error) ? error.message : 'Повторите попытку позже.'}</AlertDescription></Alert>
}
