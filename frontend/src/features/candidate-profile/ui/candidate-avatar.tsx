import { useQuery } from '@tanstack/react-query'
import { UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'

import { candidatePhotoQueryKey, getCandidatePhoto } from '@/features/candidate-profile/api/files'
import { cn } from '@/shared/lib/cn'
import { createPrivateObjectUrl, revokePrivateObjectUrl } from '@/shared/lib/private-object-url'

function usePrivateImageUrl(blob: Blob | undefined): string | null {
  const [image, setImage] = useState<{ blob?: Blob; url: string | null }>({ url: null })

  useEffect(() => {
    const url = blob ? createPrivateObjectUrl(blob) : null
    // The browser resource is created and released by the same effect, including StrictMode remounts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setImage({ blob, url })
    return () => {
      if (url) revokePrivateObjectUrl(url)
    }
  }, [blob])

  return image.blob === blob ? image.url : null
}

function initials(firstName: string | null, lastName: string | null): string {
  return [firstName, lastName]
    .filter((part): part is string => Boolean(part))
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase('ru-RU'))
    .join('')
}

export function CandidateAvatar({
  userId,
  hasPhoto,
  firstName,
  lastName,
  previewUrl,
  className,
}: {
  userId: string
  hasPhoto: boolean
  firstName: string | null
  lastName: string | null
  previewUrl?: string | null
  className?: string
}) {
  const photo = useQuery({
    queryKey: candidatePhotoQueryKey(userId),
    queryFn: ({ signal }) => getCandidatePhoto(signal),
    enabled: hasPhoto && !previewUrl,
    staleTime: 60_000,
  })
  const fetchedUrl = usePrivateImageUrl(photo.data)
  const source = previewUrl ?? fetchedUrl
  const fallback = initials(firstName, lastName)

  return (
    <div className={cn('grid size-20 shrink-0 place-items-center overflow-hidden rounded-2xl border bg-muted text-xl font-semibold text-muted-foreground', className)}>
      {source ? <img src={source} alt="Фото кандидата" className="size-full object-cover" /> : fallback ? <span aria-label={`Инициалы: ${fallback}`}>{fallback}</span> : <UserRound className="size-8" aria-label="Фото не загружено" />}
    </div>
  )
}
