import { useMutation } from '@tanstack/react-query'
import { Outlet, useNavigate } from '@tanstack/react-router'
import { ChevronDown, LogOut } from 'lucide-react'
import { useState } from 'react'
import { CandidateLayout } from '@/app/layouts/candidate-layout'
import { CabinetNavigation } from '@/app/layouts/cabinet-navigation'
import { queryClient } from '@/app/query-client'
import { logoutAccount } from '@/features/auth/api/auth'
import { companyDraft, useCompanyDraft } from '@/features/employer-company/model/company-draft'
import { CompanyUnsavedDialog } from '@/features/employer-company/ui/company-unsaved-dialog'
import { useSession } from '@/shared/session/session'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

export function CabinetLayout() {
  const user = useSession().user
  return user?.role === 'employer' ? <EmployerLayout /> : <CandidateLayout />
}

function EmployerLayout() {
  const user = useSession().user
  const navigate = useNavigate()
  const companyIsDirty = useCompanyDraft()
  const [confirmLogout, setConfirmLogout] = useState(false)
  const [savingBeforeLogout, setSavingBeforeLogout] = useState(false)
  const logout = useMutation({ mutationFn: logoutAccount, onSettled: () => { queryClient.clear(); void navigate({ to: '/login', replace: true }) } })

  function startLogout(): void {
    if (companyIsDirty) setConfirmLogout(true)
    else logout.mutate()
  }

  async function saveAndLogout(): Promise<void> {
    setSavingBeforeLogout(true)
    const saved = await companyDraft.save()
    setSavingBeforeLogout(false)
    if (!saved) return
    setConfirmLogout(false)
    logout.mutate()
  }

  function discardAndLogout(): void {
    companyDraft.discard()
    setConfirmLogout(false)
    logout.mutate()
  }

  return (
    <div className="min-h-svh">
      <header className="border-b bg-card/95">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center gap-2 px-4 sm:px-6 lg:gap-6">
          <BrandLogo className="h-7 shrink-0 sm:h-8" />
          <CabinetNavigation employer />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" className="ml-auto h-auto min-h-11 max-w-[16rem] min-w-0 gap-2 px-2" aria-label="Открыть меню аккаунта">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/10 text-sm font-semibold text-primary" aria-hidden="true">
                  {(user?.fullName || user?.email || 'Р').slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden min-w-0 text-left sm:block">
                  <span className="block truncate text-sm font-medium">{user?.fullName || user?.email}</span>
                  <span className="block text-xs font-normal text-muted-foreground">Работодатель</span>
                </span>
                <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuLabel className="font-normal">
                <p className="break-words font-medium leading-5">{user?.fullName || user?.email}</p>
                <p className="mt-1 text-xs text-muted-foreground">Кабинет работодателя</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" disabled={logout.isPending} onSelect={startLogout}>
                <LogOut aria-hidden="true" />{logout.isPending ? 'Выходим…' : 'Выйти'}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8"><Outlet /></main>
      <CompanyUnsavedDialog
        open={confirmLogout}
        saving={savingBeforeLogout}
        onSave={() => { void saveAndLogout() }}
        onDiscard={discardAndLogout}
        onStay={() => setConfirmLogout(false)}
      />
    </div>
  )
}
