import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  deleteEmployerCompanyLogo,
  employerCompanyLogoQueryKey,
  employerCompanyQueryKey,
  getEmployerCompanyLogo,
  uploadEmployerCompanyLogo,
} from '@/features/employer-company/api/company'
import { validateCompanyLogo } from '@/features/employer-company/model/logo-validation'
import type { CompanyResponse } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { createPrivateObjectUrl, revokePrivateObjectUrl } from '@/shared/lib/private-object-url'
import { usePrivateImageUrl } from '@/shared/lib/use-private-image-url'
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/ui/avatar'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

function companyInitials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]?.toLocaleUpperCase('ru-RU')).join('') || 'К'
}

export function CompanyLogo({ company, previewUrl, className }: {
  company: CompanyResponse
  previewUrl?: string | null
  className?: string
}) {
  const logo = useQuery({
    queryKey: employerCompanyLogoQueryKey(company.id),
    queryFn: ({ signal }) => getEmployerCompanyLogo(signal),
    enabled: company.has_logo && !previewUrl,
    staleTime: 60_000,
  })
  const fetchedUrl = usePrivateImageUrl(logo.data)
  const source = previewUrl ?? fetchedUrl

  return (
    <Avatar className={`size-24 rounded-2xl bg-card ${className ?? ''}`}>
      {source ? <AvatarImage src={source} alt={`Логотип компании ${company.name}`} className="object-contain p-2" /> : null}
      <AvatarFallback className="rounded-2xl bg-primary/10 text-xl text-primary">{companyInitials(company.name)}</AvatarFallback>
    </Avatar>
  )
}

export function CompanyLogoManager({ company, accountId }: { company: CompanyResponse; accountId: string }) {
  const client = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  useEffect(() => () => {
    if (previewUrl) revokePrivateObjectUrl(previewUrl)
  }, [previewUrl])

  function clearSelection(): void {
    if (previewUrl) revokePrivateObjectUrl(previewUrl)
    setFile(null)
    setPreviewUrl(null)
    setValidationError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  async function refresh(hasLogo: boolean): Promise<void> {
    client.setQueryData<CompanyResponse>(employerCompanyQueryKey(accountId), (current) => current ? { ...current, has_logo: hasLogo } : current)
    client.removeQueries({ queryKey: employerCompanyLogoQueryKey(company.id) })
    await client.invalidateQueries({ queryKey: employerCompanyQueryKey(accountId) })
  }

  const upload = useMutation({
    mutationFn: uploadEmployerCompanyLogo,
    onSuccess: async () => { clearSelection(); await refresh(true) },
  })
  const remove = useMutation({
    mutationFn: deleteEmployerCompanyLogo,
    onSuccess: async () => { await refresh(false) },
  })
  const error = upload.error ?? remove.error

  function selectFile(next: File | undefined): void {
    if (!next) return
    const message = validateCompanyLogo(next)
    setValidationError(message)
    if (previewUrl) revokePrivateObjectUrl(previewUrl)
    setFile(message ? null : next)
    setPreviewUrl(message ? null : createPrivateObjectUrl(next))
  }

  const pending = upload.isPending || remove.isPending
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <CompanyLogo company={company} previewUrl={previewUrl} />
      <div className="min-w-0 space-y-2">
        <input ref={inputRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" aria-label="Выбрать логотип" onChange={(event) => selectFile(event.target.files?.[0])} />
        <div className="flex flex-wrap gap-2">
          {file ? (
            <>
              <Button type="button" size="sm" disabled={pending} onClick={() => upload.mutate(file)}>{upload.isPending ? <Spinner label="Загружаем…" /> : 'Сохранить логотип'}</Button>
              <Button type="button" size="sm" variant="outline" disabled={pending} onClick={clearSelection}>Отмена</Button>
            </>
          ) : (
            <>
              <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => inputRef.current?.click()}><ImagePlus aria-hidden="true" />{company.has_logo ? 'Заменить' : 'Загрузить логотип'}</Button>
              {company.has_logo ? <Button type="button" size="sm" variant="ghost" className="text-destructive hover:text-destructive" disabled={pending} onClick={() => remove.mutate()}><Trash2 aria-hidden="true" />Удалить</Button> : null}
            </>
          )}
        </div>
        <p className="text-xs leading-5 text-muted-foreground">PNG, JPEG или WebP, до 5 МБ.</p>
        {validationError ? <p role="alert" className="text-xs text-destructive">{validationError}</p> : null}
        {error ? <p role="alert" className="text-xs text-destructive">{isApiError(error) ? error.message : 'Не удалось изменить логотип. Старый логотип сохранён.'}</p> : null}
      </div>
    </div>
  )
}
