export function requestOptions(signal?: AbortSignal): RequestInit {
  const timeout = AbortSignal.timeout(15_000)
  return { signal: signal ? AbortSignal.any([signal, timeout]) : timeout }
}
