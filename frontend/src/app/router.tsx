import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'

import { CandidateLayout } from '@/app/layouts/candidate-layout'
import { restoreCandidateSession } from '@/features/auth/api/auth'
import { LoginPage } from '@/features/auth/ui/login-page'
import { RegisterPage } from '@/features/auth/ui/register-page'
import { VerifyEmailPage } from '@/features/auth/ui/verify-email-page'
import { isProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import { ProfilePage } from '@/features/candidate-profile/ui/profile-page'
import { AssessmentAttemptPage } from '@/features/candidate-profile/ui/assessment-attempt-page'
import { AssessmentPage } from '@/features/candidate-profile/ui/assessment-page'
import { PrivacyPolicyPage } from '@/features/legal/ui/privacy-policy-page'
import { PersonalDataConsentPage } from '@/features/legal/ui/personal-data-consent-page'
import { PublicationConsentPage } from '@/features/legal/ui/publication-consent-page'
import { TermsPage } from '@/features/legal/ui/terms-page'

const rootRoute = createRootRoute({ component: Outlet })

async function hasCandidateSession(ignoreRestoreError = false): Promise<boolean> {
  try {
    return await restoreCandidateSession()
  } catch (error) {
    if (ignoreRestoreError) return false
    throw error
  }
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: async () => {
    if (await hasCandidateSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', search: { section: undefined }, replace: true })
    }
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw redirect({ to: '/login', replace: true })
  },
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  beforeLoad: async () => {
    if (await hasCandidateSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', search: { section: undefined }, replace: true })
    }
  },
  component: LoginPage,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  beforeLoad: async () => {
    if (await hasCandidateSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', search: { section: undefined }, replace: true })
    }
  },
  component: RegisterPage,
})

const verifyEmailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/verify-email',
  beforeLoad: async () => {
    if (await hasCandidateSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/profile', search: { section: undefined }, replace: true })
    }
  },
  component: VerifyEmailPage,
})

const privacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/privacy',
  component: PrivacyPolicyPage,
})

const termsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/terms',
  component: TermsPage,
})

const personalDataConsentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/legal/personal-data',
  component: PersonalDataConsentPage,
})

const publicationConsentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/legal/publication',
  component: PublicationConsentPage,
})

const candidateLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: '_candidate',
  beforeLoad: async () => {
    if (!(await hasCandidateSession())) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/login', replace: true })
    }
  },
  component: CandidateLayout,
})

const profileRoute = createRoute({
  getParentRoute: () => candidateLayoutRoute,
  path: '/profile',
  validateSearch: (search: Record<string, unknown>) => ({
    section: isProfileSectionId(search.section) ? search.section : undefined,
  }),
  component: ProfilePage,
})

const assessmentsRoute = createRoute({
  getParentRoute: () => candidateLayoutRoute,
  path: '/assessments',
  component: AssessmentPage,
})

const assessmentAttemptRoute = createRoute({
  getParentRoute: () => candidateLayoutRoute,
  path: '/assessments/attempts/$attemptId',
  component: AssessmentAttemptPage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  verifyEmailRoute,
  privacyRoute,
  termsRoute,
  personalDataConsentRoute,
  publicationConsentRoute,
  candidateLayoutRoute.addChildren([profileRoute, assessmentsRoute, assessmentAttemptRoute]),
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  scrollRestoration: true,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
