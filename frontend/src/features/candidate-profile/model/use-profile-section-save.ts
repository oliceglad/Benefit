import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import {
  candidateProfileQueryKey,
  getCandidateProfile,
  updateCandidateProfile,
} from '@/features/candidate-profile/api/profile'
import type { ProfileResponse, ProfileUpdate } from '@/shared/api/generated/candidates/models'

export type SaveConfirmation = 'confirmed' | 'unconfirmed' | null

export function useProfileSectionSave({
  profile,
  isDirty,
  applyProfile,
  onError,
}: {
  profile: ProfileResponse
  isDirty: boolean
  applyProfile: (profile: ProfileResponse) => void
  onError?: (error: unknown) => void
}) {
  const queryClient = useQueryClient()
  const [confirmation, setConfirmation] = useState<SaveConfirmation>(null)
  const confirmationRef = useRef<SaveConfirmation>(null)
  const [isRetryingConfirmation, setIsRetryingConfirmation] = useState(false)

  function updateConfirmation(value: SaveConfirmation): void {
    confirmationRef.current = value
    setConfirmation(value)
  }

  async function confirmSavedProfile(): Promise<boolean> {
    try {
      const confirmed = await queryClient.fetchQuery({
        queryKey: candidateProfileQueryKey,
        queryFn: ({ signal }) => getCandidateProfile(signal),
        staleTime: 0,
      })
      applyProfile(confirmed)
      updateConfirmation('confirmed')
      return true
    } catch {
      updateConfirmation('unconfirmed')
      return false
    }
  }

  const mutation = useMutation({
    mutationFn: updateCandidateProfile,
    onMutate: () => updateConfirmation(null),
    onSuccess: async (updated) => {
      queryClient.setQueryData(candidateProfileQueryKey, updated)
      applyProfile(updated)
      await confirmSavedProfile()
    },
    onError,
  })

  useEffect(() => {
    if (!isDirty && !mutation.isPending) applyProfile(profile)
  }, [applyProfile, isDirty, mutation.isPending, profile])

  async function save(update: ProfileUpdate): Promise<boolean> {
    try {
      await mutation.mutateAsync(update)
      return confirmationRef.current === 'confirmed'
    } catch {
      return false
    }
  }

  async function retryConfirmation(): Promise<boolean> {
    setIsRetryingConfirmation(true)
    const confirmed = await confirmSavedProfile()
    setIsRetryingConfirmation(false)
    return confirmed
  }

  return { ...mutation, confirmation, isRetryingConfirmation, retryConfirmation, save }
}
