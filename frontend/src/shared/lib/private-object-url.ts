const privateUrls = new Set<string>()

export function createPrivateObjectUrl(blob: Blob): string {
  const url = URL.createObjectURL(blob)
  privateUrls.add(url)
  return url
}

export function revokePrivateObjectUrl(url: string): void {
  if (!privateUrls.delete(url)) return
  URL.revokeObjectURL(url)
}

export function revokeAllPrivateObjectUrls(): void {
  privateUrls.forEach((url) => URL.revokeObjectURL(url))
  privateUrls.clear()
}

export const privateObjectUrlTestApi = {
  size(): number {
    return privateUrls.size
  },
  reset(): void {
    privateUrls.clear()
  },
}
