import { useMutation } from '@tanstack/react-query'
import { Outlet, useNavigate } from '@tanstack/react-router'
import { LogOut } from 'lucide-react'

import { queryClient } from '@/app/query-client'
import { logoutCandidate } from '@/features/auth/api/auth'
import { useSession } from '@/shared/session/session'
import { BrandLogo, BrandMark } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'

export function CandidateLayout() {
  const session = useSession()
  const navigate = useNavigate()
  const logout = useMutation({
    mutationFn: logoutCandidate,
    onSettled: () => {
      queryClient.clear()
      void navigate({ to: '/login', replace: true })
    },
  })

  return (
    <div className="min-h-svh">
      <header className="border-b bg-card/92 backdrop-blur">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <BrandLogo className="hidden h-8 sm:block" />
            <BrandMark className="size-9 shrink-0 sm:hidden" />
            <div className="min-w-0">
              <p className="truncate text-xs text-muted-foreground">Кабинет кандидата</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden min-w-0 text-right sm:block">
              <p className="max-w-64 truncate text-sm font-medium">
                {session.user?.fullName || session.user?.email || 'Кандидат'}
              </p>
              <p className="text-xs text-muted-foreground">Кандидат</p>
            </div>
            <div className="group relative">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Выйти из кабинета"
                aria-describedby="logout-tooltip"
                disabled={logout.isPending}
                onClick={() => logout.mutate()}
              >
                <LogOut aria-hidden="true" />
              </Button>
              <span
                id="logout-tooltip"
                role="tooltip"
                className="pointer-events-none absolute right-0 top-full z-20 mt-2 rounded-md bg-foreground px-2.5 py-1.5 text-xs font-medium whitespace-nowrap text-background opacity-0 shadow-md transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
              >
                Выйти
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-7 sm:px-6 sm:py-10">
        <Outlet />
      </main>
    </div>
  )
}
