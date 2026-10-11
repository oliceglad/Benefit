import { useEffect, useRef, useSyncExternalStore } from 'react'

type CompanyDraftHandlers = {
  save: () => Promise<boolean>
  discard: () => void
}

class CompanyDraftCoordinator {
  private handlers: CompanyDraftHandlers | null = null
  private dirty = false
  private readonly listeners = new Set<() => void>()

  getSnapshot = (): boolean => this.dirty

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  register(handlers: CompanyDraftHandlers): () => void {
    this.handlers = handlers
    this.setDirty(false)
    return () => {
      if (this.handlers !== handlers) return
      this.handlers = null
      this.setDirty(false)
    }
  }

  setDirty(dirty: boolean): void {
    if (this.dirty === dirty) return
    this.dirty = dirty
    this.listeners.forEach((listener) => listener())
  }

  save(): Promise<boolean> {
    return this.handlers?.save() ?? Promise.resolve(true)
  }

  discard(): void {
    this.handlers?.discard()
    this.setDirty(false)
  }
}

export const companyDraft = new CompanyDraftCoordinator()

export function useCompanyDraft(): boolean {
  return useSyncExternalStore(
    companyDraft.subscribe,
    companyDraft.getSnapshot,
    companyDraft.getSnapshot,
  )
}

export function useRegisterCompanyDraft(
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
    () => companyDraft.register({
      save: () => saveRef.current(),
      discard: () => discardRef.current(),
    }),
    [],
  )

  useEffect(() => companyDraft.setDirty(isDirty), [isDirty])
}
