import { useSyncExternalStore } from 'react'

type VerificationSnapshot = {
  email: string
  resendAvailableAt: number
  codeExpiresAt: number | null
  resendCooldownSeconds: number
}

const emptySnapshot: VerificationSnapshot = {
  email: '',
  resendAvailableAt: 0,
  codeExpiresAt: null,
  resendCooldownSeconds: 60,
}

class VerificationFlow {
  private snapshot = emptySnapshot
  private readonly listeners = new Set<() => void>()

  getSnapshot = (): VerificationSnapshot => this.snapshot

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  start(email: string, codeExpiresIn: number, resendAvailableIn: number): void {
    const now = Date.now()
    this.snapshot = {
      email,
      resendAvailableAt: now + resendAvailableIn * 1000,
      codeExpiresAt: now + codeExpiresIn * 1000,
      resendCooldownSeconds: resendAvailableIn,
    }
    this.emit()
  }

  setEmail(email: string): void {
    this.snapshot = { ...this.snapshot, email }
    this.emit()
  }

  markResent(seconds = this.snapshot.resendCooldownSeconds): void {
    this.snapshot = {
      ...this.snapshot,
      resendAvailableAt: Date.now() + seconds * 1000,
      resendCooldownSeconds: seconds,
    }
    this.emit()
  }

  clear(): void {
    this.snapshot = emptySnapshot
    this.emit()
  }

  private emit(): void {
    this.listeners.forEach((listener) => listener())
  }
}

export const verificationFlow = new VerificationFlow()

export function useVerificationFlow(): VerificationSnapshot {
  return useSyncExternalStore(
    verificationFlow.subscribe,
    verificationFlow.getSnapshot,
    verificationFlow.getSnapshot,
  )
}
