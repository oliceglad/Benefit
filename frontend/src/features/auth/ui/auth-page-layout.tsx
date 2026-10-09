import type { ReactNode } from 'react'

import { LegalLinks } from '@/features/legal/ui/legal-links'
import { BrandLogo } from '@/shared/ui/brand-logo'

export function AuthPageLayout({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-svh lg:grid-cols-[minmax(0,1.05fr)_minmax(440px,0.95fr)]">
      <section className="hidden min-h-svh grid-rows-[auto_minmax(0,1fr)] bg-primary px-12 py-8 text-primary-foreground lg:grid">
        <div>
          <BrandLogo inverse className="h-9" />
        </div>
        <div className="flex min-h-0 items-center py-8">
          <div className="max-w-xl space-y-5">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-white/70">
              Кабинет кандидата
            </p>
            <h1 className="text-4xl font-semibold leading-tight xl:text-5xl">
              Профиль, который работает на вашу карьеру
            </h1>
            <p className="max-w-lg text-lg leading-8 text-white/78">
              Управляйте контактами и данными профиля в одном пространстве.
            </p>
          </div>
        </div>
      </section>

      <section className="flex min-h-svh items-center justify-center px-4 py-8 sm:px-8">
        <div className="w-full max-w-md space-y-5">
          <div className="px-1 lg:hidden">
            <BrandLogo className="h-9" />
          </div>
          {children}
          <LegalLinks />
        </div>
      </section>
    </main>
  )
}
