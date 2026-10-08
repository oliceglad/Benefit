import { useEffect, useState } from 'react'

function secondsUntil(timestamp: number, now: number): number {
  return Math.max(0, Math.ceil((timestamp - now) / 1000))
}

export function useCountdown(timestamp: number): number {
  const [now, setNow] = useState(Date.now)

  useEffect(() => {
    const interval = window.setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => window.clearInterval(interval)
  }, [])

  return secondsUntil(timestamp, now)
}
