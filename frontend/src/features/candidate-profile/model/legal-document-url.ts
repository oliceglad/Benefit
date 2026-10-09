export function resolveDocumentUrl(value: string, origin = window.location.origin): string | null {
  try {
    const candidate = value.trim()
    if (!candidate) return null
    const isSameOriginPath = candidate.startsWith('/') && !candidate.startsWith('//')
    const url = isSameOriginPath ? new URL(candidate, origin) : new URL(candidate)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch {
    return null
  }
}
