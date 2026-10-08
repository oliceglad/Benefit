import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'

import { CandidateLayout } from '@/app/layouts/candidate-layout'
import { LoginPage } from '@/features/auth/ui/login-page'
import { RegisterPage } from '@/features/auth/ui/register-page'
import { VerifyEmailPage } from '@/features/auth/ui/verify-email-page'
import { ProfilePage } from '@/features/candidate-profile/ui/profile-page'
import { session } from '@/shared/session/session'

const rootRoute = createRootRoute({ component: Outlet })

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    // TanStack Router uses redirect response objects for control flow.
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw redirect({
      to: session.getSnapshot().tokens ? '/profile' : '/login',
      replace: true,
    })
  },
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  beforeLoad: () => {
    if (session.getSnapshot().tokens) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', replace: true })
    }
  },
  component: LoginPage,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  beforeLoad: () => {
    if (session.getSnapshot().tokens) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', replace: true })
    }
  },
  component: RegisterPage,
})

const verifyEmailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/verify-email',
  beforeLoad: () => {
    if (session.getSnapshot().tokens) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', replace: true })
    }
  },
  component: VerifyEmailPage,
})

const candidateLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: '_candidate',
  beforeLoad: () => {
    if (!session.getSnapshot().tokens) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/login', replace: true })
    }
  },
  component: CandidateLayout,
})

const profileRoute = createRoute({
  getParentRoute: () => candidateLayoutRoute,
  path: '/profile',
  component: ProfilePage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  verifyEmailRoute,
  candidateLayoutRoute.addChildren([profileRoute]),
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
