import { useMutation, useQuery } from '@tanstack/react-query'
import { Outlet, useNavigate, useRouterState } from '@tanstack/react-router'
import { ArrowLeft, ChevronDown, LogOut } from 'lucide-react'
import { useState } from 'react'

import { queryClient } from '@/app/query-client'
import { candidateBackLink } from '@/app/layouts/candidate-navigation'
import { CabinetNavigation } from '@/app/layouts/cabinet-navigation'
import { logoutAccount } from '@/features/auth/api/auth'
import { candidateProfileQueryKey, getCandidateProfile } from '@/features/candidate-profile/api/profile'
import { profileDraft, useProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import { isProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import { CandidateAvatar } from '@/features/candidate-profile/ui/candidate-avatar'
import { UnsavedChangesDialog } from '@/features/candidate-profile/ui/unsaved-changes-dialog'
import { BrandGuide } from '@/features/platform-guide/ui/brand-guide'
import { useSession } from '@/shared/session/session'
import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

export function CandidateLayout() {
  const session = useSession()
  const draft = useProfileDraft()
  const navigate = useNavigate()
  const location = useRouterState({ select: (state) => state.location })
  const pathname = location.pathname
  const mobileProfileSection = pathname === '/profile' && isProfileSectionId(location.search.section)
  const backLink = candidateBackLink(pathname)
  const [confirmLogout, setConfirmLogout] = useState(false)
  const [savingBeforeLogout, setSavingBeforeLogout] = useState(false)
  const profile = useQuery({
    queryKey: candidateProfileQueryKey,
    queryFn: ({ signal }) => getCandidateProfile(signal),
    enabled: session.status === 'authenticated' && session.user?.role === 'candidate',
  })
  const logout = useMutation({
    mutationFn: logoutAccount,
    onSettled: () => {
      queryClient.clear()
      void navigate({ to: '/login', replace: true })
    },
  })
  const accountName = [profile.data?.first_name, profile.data?.last_name]
    .filter(Boolean)
    .join(' ') || session.user?.fullName || session.user?.email || 'Кандидат'

  function startLogout(): void {
    if (draft.isDirty) setConfirmLogout(true)
    else logout.mutate()
  }

  async function saveAndLogout(): Promise<void> {
    setSavingBeforeLogout(true)
    const saved = await profileDraft.save()
    setSavingBeforeLogout(false)
    if (!saved) return
    profileDraft.forceClean()
    setConfirmLogout(false)
    logout.mutate()
  }

  function discardAndLogout(): void {
    profileDraft.discard()
    profileDraft.forceClean()
    setConfirmLogout(false)
    logout.mutate()
  }

  function navigateBack(): void {
    if (backLink?.destination === 'assessments') {
      void navigate({ to: '/assessments' })
    } else if (backLink?.destination === 'skills') {
      void navigate({ to: '/profile', search: { section: 'skills' } })
    }
  }

  return (
    <div className="min-h-svh">
      <header className={`border-b bg-card/92 backdrop-blur ${mobileProfileSection ? 'hidden lg:block' : ''}`}>
        <div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <BrandGuide role="candidate" className="shrink-0" />
            <p className="hidden truncate text-xs text-muted-foreground sm:block">Кабинет кандидата</p>
          </div>

          <CandidateAccountMenu
            userId={profile.data?.user_id ?? session.user?.id ?? 'candidate'}
            hasPhoto={profile.data?.has_photo ?? false}
            firstName={profile.data?.first_name ?? session.user?.fullName?.split(/\s+/)[0] ?? null}
            lastName={profile.data?.last_name ?? session.user?.fullName?.split(/\s+/)[1] ?? null}
            accountName={accountName}
            pending={logout.isPending}
            onLogout={startLogout}
          />
        </div>
        <div className="mx-auto max-w-6xl px-4 sm:px-6"><CabinetNavigation /></div>
      </header>

      <main className={`mx-auto max-w-6xl px-4 sm:px-6 ${mobileProfileSection ? 'py-0 lg:py-10' : 'py-6 sm:py-10'}`}>
        {backLink ? (
          <nav aria-label="Возврат к предыдущему экрану" className="mb-4">
            <Button type="button" variant="outline" size="sm" onClick={navigateBack}>
              <ArrowLeft aria-hidden="true" />
              {backLink.label}
            </Button>
          </nav>
        ) : null}
        <Outlet />
      </main>
      <UnsavedChangesDialog
        open={confirmLogout}
        saving={savingBeforeLogout}
        onSave={() => void saveAndLogout()}
        onDiscard={discardAndLogout}
        onStay={() => setConfirmLogout(false)}
      />
    </div>
  )
}

export function CandidateAccountMenu({
  userId,
  hasPhoto,
  firstName,
  lastName,
  accountName,
  pending,
  onLogout,
}: {
  userId: string
  hasPhoto: boolean
  firstName: string | null
  lastName: string | null
  accountName: string
  pending: boolean
  onLogout: () => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" className="h-auto min-h-11 max-w-[17rem] gap-1.5 rounded-xl px-1.5 py-1 sm:gap-2 sm:px-2" aria-label="Открыть меню аккаунта">
          <CandidateAvatar
            userId={userId}
            hasPhoto={hasPhoto}
            firstName={firstName}
            lastName={lastName}
            className="size-10 rounded-full text-sm"
          />
          <span className="hidden min-w-0 text-left sm:block">
            <span className="block truncate text-sm font-medium">{accountName}</span>
            <span className="block text-xs font-normal text-muted-foreground">Кандидат</span>
          </span>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="font-normal">
          <p className="break-words font-medium leading-5">{accountName}</p>
          <p className="mt-1 text-xs text-muted-foreground">Кандидат</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" disabled={pending} onSelect={onLogout}>
          <LogOut aria-hidden="true" />
          {pending ? 'Выходим…' : 'Выйти'}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
