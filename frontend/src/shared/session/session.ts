import { useSyncExternalStore } from 'react'

export type SessionTokens = {
  accessToken: string
  refreshToken: string
  expiresIn: number
  refreshExpiresIn: number
}

export type SessionUser = {
  id: string
  email: string
  role: string
  fullName?: string | null
  isEmailVerified: boolean
}

export type SessionSnapshot = {
  tokens: SessionTokens | null
  user: SessionUser | null
}

class MemorySession {
  private snapshot: SessionSnapshot = { tokens: null, user: null }
  private revision = 0
  private readonly listeners = new Set<() => void>()

  getSnapshot = (): SessionSnapshot => this.snapshot

  getRevision = (): number => this.revision

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  setTokens(tokens: SessionTokens): void {
    this.snapshot = { ...this.snapshot, tokens }
    this.revision += 1
    this.emit()
  }

  replaceTokensIfCurrent(
    tokens: SessionTokens,
    expectedRevision: number,
    expectedRefreshToken: string,
  ): boolean {
    if (
      this.revision !== expectedRevision ||
      this.snapshot.tokens?.refreshToken !== expectedRefreshToken
    ) {
      return false
    }
    this.snapshot = { ...this.snapshot, tokens }
    this.revision += 1
    this.emit()
    return true
  }

  setUser(user: SessionUser): void {
    this.snapshot = { ...this.snapshot, user }
    this.revision += 1
    this.emit()
  }

  clear(): void {
    this.snapshot = { tokens: null, user: null }
    this.revision += 1
    this.emit()
  }

  clearIfCurrent(expectedRevision: number, expectedRefreshToken: string): boolean {
    if (
      this.revision !== expectedRevision ||
      this.snapshot.tokens?.refreshToken !== expectedRefreshToken
    ) {
      return false
    }
    this.clear()
    return true
  }

  private emit(): void {
    this.listeners.forEach((listener) => listener())
  }
}

export const session = new MemorySession()

export function useSession(): SessionSnapshot {
  return useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot)
}
