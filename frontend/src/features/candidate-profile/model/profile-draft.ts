import { useEffect, useRef, useSyncExternalStore } from 'react'

import type { ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'

type DraftHandlers = {
  section: ProfileSectionId
  save: () => Promise<boolean>
  discard: () => void
}

export type DraftSnapshot = {
  section: ProfileSectionId | null
  isDirty: boolean
}

const emptySnapshot: DraftSnapshot = { section: null, isDirty: false }

class ProfileDraftCoordinator {
  private handlers: DraftHandlers | null = null
  private snapshot = emptySnapshot
  private readonly listeners = new Set<() => void>()

  getSnapshot = (): DraftSnapshot => this.snapshot

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  register(handlers: DraftHandlers): () => void {
    this.handlers = handlers
    this.snapshot = { section: handlers.section, isDirty: false }
    this.emit()
    return () => {
      if (this.handlers === handlers) {
        this.handlers = null
        this.snapshot = emptySnapshot
        this.emit()
      }
    }
  }

  setDirty(section: ProfileSectionId, isDirty: boolean): void {
    if (this.handlers?.section !== section || this.snapshot.isDirty === isDirty) return
    this.snapshot = { section, isDirty }
    this.emit()
  }

  async save(): Promise<boolean> {
    return this.handlers ? this.handlers.save() : true
  }

  discard(): void {
    this.handlers?.discard()
  }

  forceClean(): void {
    if (!this.snapshot.isDirty) return
    this.snapshot = { ...this.snapshot, isDirty: false }
    this.emit()
  }

  private emit(): void {
    this.listeners.forEach((listener) => listener())
  }
}

export const profileDraft = new ProfileDraftCoordinator()

export function useProfileDraft(): DraftSnapshot {
  return useSyncExternalStore(
    profileDraft.subscribe,
    profileDraft.getSnapshot,
    profileDraft.getSnapshot,
  )
}

export function useRegisterProfileDraft(
  section: ProfileSectionId,
  isDirty: boolean,
  save: () => Promise<boolean>,
  discard: () => void,
): void {
  const saveRef = useRef(save)
  const discardRef = useRef(discard)

  useEffect(() => {
    saveRef.current = save
    discardRef.current = discard
  }, [discard, save])

  useEffect(
    () => profileDraft.register({
      section,
      save: () => saveRef.current(),
      discard: () => discardRef.current(),
    }),
    [section],
  )

  useEffect(() => profileDraft.setDirty(section, isDirty), [isDirty, section])
}
