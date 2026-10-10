import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  candidateConsentsQueryKey, candidateProfileQueryKey, getCandidateConsents,
  getCandidateProfile, updateCandidateProfile,
} from '@/features/candidate-profile/api/profile'
import { buildJuryStepUpdate, juryToolsEnabled } from '@/features/candidate-profile/model/jury-demo-data'
import { missingFieldLabel, profileSectionIds, type ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import { isApiError } from '@/shared/api/transport/api-error'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

export function JuryStepTools(props: {
  section: ProfileSectionId
  completed: boolean
  dirty: boolean
  onPendingChange: (pending: boolean) => void
}) {
  return juryToolsEnabled() && !props.completed ? <EnabledJuryStepTools key={props.section} {...props} /> : null
}

function EnabledJuryStepTools({ section, dirty, onPendingChange }: {
  section: ProfileSectionId
  dirty: boolean
  onPendingChange: (pending: boolean) => void
}) {
  const queryClient = useQueryClient()
  const readinessStep = section === 'consents'
  const action = useMutation({
    mutationFn: async () => {
      const update = buildJuryStepUpdate(section)
      if (update) return { profile: await updateCandidateProfile(update), consents: undefined }
      const [profile, consents] = await Promise.all([getCandidateProfile(), getCandidateConsents()])
      return { profile, consents }
    },
    onSuccess: ({ profile, consents }) => {
      queryClient.setQueryData(candidateProfileQueryKey, profile)
      if (consents) queryClient.setQueryData(candidateConsentsQueryKey, consents)
    },
  })

  useEffect(() => {
    onPendingChange(action.isPending)
    return () => onPendingChange(false)
  }, [action.isPending, onPendingChange])

  const missing = action.data?.profile.completeness.missing_required.map(missingFieldLabel) ?? []
  const result = readinessStep
    ? missing.length ? `Осталось заполнить: ${missing.join(', ')}.`
      : action.data?.profile.status === 'published' ? 'Профиль опубликован.' : 'Профиль готов к публикации.'
    : 'Текущий шаг заполнен тестовыми данными и сохранён.'

  return (
    <aside aria-label="Инструменты жюри" className="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold">Для тестеров и жюри · шаг {profileSectionIds.indexOf(section) + 1} из 7</p>
          <p className="text-sm text-muted-foreground">{readinessStep
            ? 'Проверьте готовность. Согласия и публикация подтверждаются вручную ниже.'
            : 'Заменит и сохранит данные только этого шага. Все подставляемые сведения вымышлены.'}</p>
        </div>
        <Button type="button" variant="outline" disabled={dirty || action.isPending} onClick={() => action.mutate()}>
          {action.isPending ? <Spinner label={readinessStep ? 'Проверяем…' : 'Заполняем…'} />
            : readinessStep ? 'Проверить готовность' : 'Заполнить шаг тестовыми данными'}
        </Button>
      </div>
      {dirty ? <p className="text-sm text-muted-foreground">Сначала сохраните введённые изменения.</p> : null}
      {action.isError ? <p role="alert" className="text-sm text-destructive">{isApiError(action.error) ? action.error.message : 'Не удалось выполнить действие. Повторите попытку.'}</p> : null}
      {action.isSuccess && !dirty ? <p role="status" className="text-sm">{result}</p> : null}
    </aside>
  )
}
