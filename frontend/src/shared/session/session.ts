import { useSyncExternalStore } from 'react'

export type SessionUser = {
  id: string
  email: string
  role: string
  fullName?: string | null
  isEmailVerified: boolean
}

export type SessionStatus = 'unknown' | 'authenticated' | 'anonymous'

export type SessionSnapshot = {
  status: SessionStatus
  user: SessionUser | null
}

class CookieSession {
  private snapshot: SessionSnapshot = { status: 'unknown', user: null }
  private revision = 0
  private readonly listeners = new Set<() => void>()

  getSnapshot = (): SessionSnapshot => this.snapshot

  getRevision = (): number => this.revision

  isRevisionCurrent(revision: number): boolean {
    return this.revision === revision
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  setUnknown(): void {
    this.update({ status: 'unknown', user: null })
  }

  setAuthenticated(user: SessionUser): void {
    this.update({ status: 'authenticated', user })
  }

  setAnonymous(): void {
    this.update({ status: 'anonymous', user: null })
  }

  setAnonymousIfCurrent(expectedRevision: number): boolean {
    if (!this.isRevisionCurrent(expectedRevision)) return false
    this.setAnonymous()
    return true
  }

  clear(): void {
    this.setAnonymous()
  }

  reset(): void {
    this.update({ status: 'unknown', user: null })
  }

  private update(snapshot: SessionSnapshot): void {
    this.snapshot = snapshot
    this.revision += 1
    this.listeners.forEach((listener) => listener())
  }
}

export const session = new CookieSession()

export function useSession(): SessionSnapshot {
  return useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot)
}
