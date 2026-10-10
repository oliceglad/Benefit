import { useMutation } from '@tanstack/react-query'
import { Outlet, useNavigate } from '@tanstack/react-router'
import { LogOut } from 'lucide-react'
import { CandidateLayout } from '@/app/layouts/candidate-layout'
import { CabinetNavigation } from '@/app/layouts/cabinet-navigation'
import { queryClient } from '@/app/query-client'
import { logoutAccount } from '@/features/auth/api/auth'
import { useSession } from '@/shared/session/session'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'

export function CabinetLayout() {
  const user = useSession().user
  return user?.role === 'employer' ? <EmployerLayout /> : <CandidateLayout />
}

function EmployerLayout() {
  const user = useSession().user
  const navigate = useNavigate()
  const logout = useMutation({ mutationFn: logoutAccount, onSettled: () => { queryClient.clear(); void navigate({ to: '/login', replace: true }) } })
  return <div className="min-h-svh"><header className="border-b bg-card/95"><div className="mx-auto max-w-6xl px-4 sm:px-6"><div className="flex min-h-16 items-center justify-between gap-4"><div className="flex items-center gap-3"><BrandLogo className="h-8" /><span className="hidden text-xs text-muted-foreground sm:block">Кабинет работодателя</span></div><div className="flex min-w-0 items-center gap-3"><span className="hidden max-w-56 truncate text-sm sm:block">{user?.fullName || user?.email}</span><Button size="sm" variant="ghost" disabled={logout.isPending} onClick={() => logout.mutate()}><LogOut aria-hidden="true" />Выйти</Button></div></div><CabinetNavigation employer /></div></header><main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10"><Outlet /></main></div>
}
