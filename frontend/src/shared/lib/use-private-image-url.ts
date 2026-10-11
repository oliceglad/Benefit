import { useEffect, useState } from 'react'

import { createPrivateObjectUrl, revokePrivateObjectUrl } from '@/shared/lib/private-object-url'

export function usePrivateImageUrl(blob: Blob | undefined): string | null {
  const [image, setImage] = useState<{ blob?: Blob; url: string | null }>({ url: null })

  useEffect(() => {
    const url = blob ? createPrivateObjectUrl(blob) : null
    // The URL and its cleanup belong to the same effect, including StrictMode remounts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setImage({ blob, url })
    return () => {
      if (url) revokePrivateObjectUrl(url)
    }
  }, [blob])

  return image.blob === blob ? image.url : null
}
