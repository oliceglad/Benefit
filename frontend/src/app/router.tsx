import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  redirect,
} from '@tanstack/react-router'

import { CandidateLayout } from '@/app/layouts/candidate-layout'
import { CabinetLayout } from '@/app/layouts/cabinet-layout'
import { restoreAccountSession } from '@/features/auth/api/auth'
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
import { vacancySearchSchema } from '@/features/vacancies/model/vacancy-search'
import { talentSearchSchema } from '@/features/talent/model/talent-search'
import { session } from '@/shared/session/session'

const rootRoute = createRootRoute({ component: Outlet })

function homeRedirect() {
  return session.getSnapshot().user?.role === 'employer'
    ? redirect({ to: '/vacancies', search: { offset: 0 }, replace: true })
    : redirect({ to: '/profile', search: { section: undefined }, replace: true })
}

async function hasAccountSession(ignoreRestoreError = false): Promise<boolean> {
  try {
    return await restoreAccountSession()
  } catch (error) {
    if (ignoreRestoreError) return false
    throw error
  }
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: async () => {
    if (await hasAccountSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw homeRedirect()
    }
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw redirect({ to: '/login', replace: true })
  },
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  beforeLoad: async () => {
    if (await hasAccountSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw homeRedirect()
    }
  },
  component: LoginPage,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  beforeLoad: async () => {
    if (await hasAccountSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw homeRedirect()
    }
  },
  component: RegisterPage,
})

const verifyEmailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/verify-email',
  beforeLoad: async () => {
    if (await hasAccountSession(true)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw homeRedirect()
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
    if (!(await hasAccountSession())) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/login', replace: true })
    }
    if (session.getSnapshot().user?.role !== 'candidate') {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw homeRedirect()
    }
  },
  component: CandidateLayout,
})

const cabinetLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: '_cabinet',
  beforeLoad: async () => {
    if (!(await hasAccountSession())) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/login', replace: true })
    }
  },
  component: CabinetLayout,
})

const vacanciesRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/vacancies',
  validateSearch: (search: Record<string, unknown>) => vacancySearchSchema.parse(search),
  component: lazyRouteComponent(() => import('@/features/vacancies/ui/vacancies-page'), 'VacanciesPage'),
})
const vacancyDetailRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/vacancies/$vacancyId',
  component: lazyRouteComponent(() => import('@/app/pages/vacancy-page'), 'VacancyPage'),
})
const messagesRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/messages',
  component: lazyRouteComponent(() => import('@/features/chat/ui/messages-page'), 'MessagesPage'),
})
const messageThreadRoute = createRoute({
  getParentRoute: () => messagesRoute, path: '/$conversationId',
})
function requireEmployer() {
  if (session.getSnapshot().user?.role !== 'employer') {
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw redirect({ to: '/vacancies', search: { offset: 0 } })
  }
}
const talentRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/talent',
  beforeLoad: requireEmployer,
  validateSearch: (search: Record<string, unknown>) => talentSearchSchema.parse(search),
  component: lazyRouteComponent(() => import('@/features/talent/ui/talent-page'), 'TalentPage'),
})
const vacancyCreateRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/vacancies/new',
  beforeLoad: requireEmployer,
  component: lazyRouteComponent(() => import('@/features/vacancies/ui/vacancy-editor-page'), 'VacancyEditorPage'),
})
const vacancyEditRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/vacancies/$vacancyId/edit',
  beforeLoad: requireEmployer,
  component: lazyRouteComponent(() => import('@/features/vacancies/ui/vacancy-editor-page'), 'VacancyEditorPage'),
})
const pipelinesRoute = createRoute({
  getParentRoute: () => cabinetLayoutRoute, path: '/pipelines',
  beforeLoad: () => {
    if (session.getSnapshot().user?.role !== 'employer') {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw redirect({ to: '/vacancies', search: { offset: 0 } })
    }
  },
  component: lazyRouteComponent(() => import('@/features/pipelines/ui/pipelines-page'), 'PipelinesPage'),
})

const pipelineDesignPreviewRoute = import.meta.env.DEV ? createRoute({
  getParentRoute: () => rootRoute, path: '/preview/pipelines',
  beforeLoad: async () => { await hasAccountSession(true) },
  component: lazyRouteComponent(() => import('@/app/layouts/pipeline-design-preview'), 'PipelineDesignPreview'),
}) : null

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

// An isolated local design review; production has no unauthenticated employer route.
const companyDesignPreviewRoute = import.meta.env.DEV ? createRoute({
  getParentRoute: () => rootRoute,
  path: '/preview/company',
  component: lazyRouteComponent(
    () => import('@/features/employer-company/ui/company-design-preview'),
    'CompanyDesignPreview',
  ),
}) : null

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  verifyEmailRoute,
  privacyRoute,
  termsRoute,
  personalDataConsentRoute,
  publicationConsentRoute,
  ...(companyDesignPreviewRoute ? [companyDesignPreviewRoute] : []),
  ...(pipelineDesignPreviewRoute ? [pipelineDesignPreviewRoute] : []),
  cabinetLayoutRoute.addChildren([talentRoute, vacanciesRoute, vacancyCreateRoute, vacancyEditRoute, vacancyDetailRoute, pipelinesRoute, messagesRoute.addChildren([messageThreadRoute])]),
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
