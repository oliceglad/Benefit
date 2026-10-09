import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  candidatePhotoQueryKey,
  deleteCandidatePhoto,
  uploadCandidatePhoto,
} from '@/features/candidate-profile/api/files'
import { candidateProfileQueryKey } from '@/features/candidate-profile/api/profile'
import { validatePhotoFile } from '@/features/candidate-profile/model/file-validation'
import { CandidateAvatar } from '@/features/candidate-profile/ui/candidate-avatar'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { createPrivateObjectUrl, revokePrivateObjectUrl } from '@/shared/lib/private-object-url'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'
import { Spinner } from '@/shared/ui/spinner'

export function PhotoManager({ profile }: { profile: ProfileResponse }) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => () => {
    if (previewUrl) revokePrivateObjectUrl(previewUrl)
  }, [previewUrl])

  async function refreshPhoto(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: candidateProfileQueryKey }),
      queryClient.invalidateQueries({ queryKey: candidatePhotoQueryKey(profile.user_id) }),
    ])
  }

  const upload = useMutation({
    mutationFn: uploadCandidatePhoto,
    onSuccess: async () => {
      clearSelection()
      await refreshPhoto()
    },
  })
  const remove = useMutation({
    mutationFn: deleteCandidatePhoto,
    onSuccess: async () => {
      setConfirmDelete(false)
      queryClient.setQueryData<ProfileResponse>(candidateProfileQueryKey, (current) => current ? { ...current, has_photo: false } : current)
      queryClient.removeQueries({ queryKey: candidatePhotoQueryKey(profile.user_id) })
      await refreshPhoto()
    },
  })
  const error = upload.error ?? remove.error

  function chooseFile(next: File | undefined): void {
    if (!next) return
    const message = validatePhotoFile(next)
    setValidationError(message)
    if (previewUrl) revokePrivateObjectUrl(previewUrl)
    setPreviewUrl(message ? null : createPrivateObjectUrl(next))
    setFile(message ? null : next)
  }

  function clearSelection(): void {
    if (previewUrl) revokePrivateObjectUrl(previewUrl)
    setPreviewUrl(null)
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="flex w-16 shrink-0 flex-col items-center gap-2 sm:w-20">
      <div className="relative">
        <CandidateAvatar userId={profile.user_id} hasPhoto={profile.has_photo} firstName={profile.first_name} lastName={profile.last_name} previewUrl={previewUrl} className="size-16 rounded-full text-lg sm:size-20" />
      <input ref={inputRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" aria-label="Выбрать фото" onChange={(event) => chooseFile(event.target.files?.[0])} />
      {!file ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" size="icon" variant="outline" className="absolute -bottom-1 -right-1 size-9 min-h-9 rounded-full bg-card p-0" aria-label="Изменить фото" disabled={upload.isPending || remove.isPending}>
              <Camera aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuItem onSelect={() => { setValidationError(null); inputRef.current?.click() }}>
              <Upload aria-hidden="true" />{profile.has_photo ? 'Заменить фото' : 'Загрузить фото'}
            </DropdownMenuItem>
            {profile.has_photo ? (
              <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)}>
                <Trash2 aria-hidden="true" />Удалить фото
              </DropdownMenuItem>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
      </div>
      {file ? (
        <div className="flex w-full flex-col gap-1">
          <Button type="button" size="sm" className="h-auto min-h-9 whitespace-normal px-1 py-1 text-[11px]" disabled={upload.isPending} onClick={() => upload.mutate(file)}>{upload.isPending ? <Spinner label="Загружаем…" /> : 'Загрузить'}</Button>
          <Button type="button" size="sm" variant="ghost" className="h-auto min-h-9 px-1 py-1 text-[11px]" disabled={upload.isPending} onClick={clearSelection}>Отмена</Button>
        </div>
      ) : null}
      {validationError ? <p className="text-center text-xs leading-4 text-destructive">{validationError}</p> : null}
      {error ? <p className="text-center text-xs leading-4 text-destructive">{isApiError(error) ? error.message : 'Не удалось изменить фото.'}</p> : null}

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Удалить фото?</AlertDialogTitle><AlertDialogDescription>Фото исчезнет из профиля. Позже можно будет загрузить новое.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel disabled={remove.isPending}>Отмена</AlertDialogCancel><AlertDialogAction className="bg-destructive text-white hover:bg-destructive/90" disabled={remove.isPending} onClick={() => remove.mutate()}>{remove.isPending ? 'Удаляем…' : 'Удалить'}</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
