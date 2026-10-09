import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { LEGAL_DOCUMENT_UPDATED_AT, LEGAL_DOCUMENT_VERSION, type LegalSection } from '@/features/legal/model/legal-documents'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'

const operatorName = (import.meta.env.VITE_LEGAL_OPERATOR_NAME as string | undefined)?.trim()
const operatorAddress = (import.meta.env.VITE_LEGAL_OPERATOR_ADDRESS as string | undefined)?.trim()
const contactEmail = (import.meta.env.VITE_LEGAL_CONTACT_EMAIL as string | undefined)?.trim()

export function LegalPageLayout({
  title,
  lead,
  sections,
  children,
}: {
  title: string
  lead: string
  sections: readonly LegalSection[]
  children?: ReactNode
}) {
  return (
    <main className="min-h-svh bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto flex min-h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" aria-label="На главную Benefit"><BrandLogo className="h-8" /></Link>
          <Button type="button" size="sm" variant="outline" asChild><Link to="/login">Войти</Link></Button>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">
        <article className="bg-card sm:rounded-2xl sm:border sm:p-8 sm:shadow-card lg:p-10">
          <header className="border-b pb-6">
            <p className="text-sm font-medium text-primary">Документы Benefit</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-muted-foreground">{lead}</p>
            <p className="mt-4 text-sm text-muted-foreground">Редакция от {LEGAL_DOCUMENT_UPDATED_AT} · версия {LEGAL_DOCUMENT_VERSION}</p>
          </header>

          <nav className="border-b py-6" aria-label="Содержание документа">
            <h2 className="text-base font-semibold">Содержание</h2>
            <ol className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              {sections.map((section) => (
                <li key={section.id}><a className="text-primary underline-offset-4 hover:underline" href={`#${section.id}`}>{section.title}</a></li>
              ))}
            </ol>
          </nav>

          <div className="space-y-8 py-7">
            {sections.map((section) => (
              <section key={section.id} id={section.id} className="scroll-mt-6" aria-labelledby={`${section.id}-title`}>
                <h2 id={`${section.id}-title`} className="text-xl font-semibold">{section.title}</h2>
                {section.paragraphs?.map((paragraph) => <p key={paragraph} className="mt-3 text-base leading-7 text-foreground/90">{paragraph}</p>)}
                {section.items ? (
                  <ul className="mt-3 list-disc space-y-2 pl-5 text-base leading-7 text-foreground/90">
                    {section.items.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                ) : null}
              </section>
            ))}
            {children}
            <LegalContacts />
          </div>

          <footer className="flex flex-wrap gap-x-5 gap-y-2 border-t pt-6 text-sm">
            <Link className="font-medium text-primary hover:underline" to="/privacy">Политика конфиденциальности</Link>
            <Link className="font-medium text-primary hover:underline" to="/terms">Пользовательское соглашение</Link>
          </footer>
        </article>
      </div>
    </main>
  )
}

function LegalContacts() {
  return (
    <section id="contacts" className="scroll-mt-6" aria-labelledby="legal-contacts-title">
      <h2 id="legal-contacts-title" className="text-xl font-semibold">Контакты оператора</h2>
      {operatorName || operatorAddress || contactEmail ? (
        <dl className="mt-3 grid gap-2 text-base leading-7 sm:grid-cols-[180px_minmax(0,1fr)]">
          {operatorName ? <><dt className="text-muted-foreground">Оператор</dt><dd>{operatorName}</dd></> : null}
          {operatorAddress ? <><dt className="text-muted-foreground">Адрес</dt><dd>{operatorAddress}</dd></> : null}
          {contactEmail ? <><dt className="text-muted-foreground">Электронная почта</dt><dd><a className="text-primary hover:underline" href={`mailto:${contactEmail}`}>{contactEmail}</a></dd></> : null}
        </dl>
      ) : (
        <p className="mt-3 rounded-xl border border-warning/35 bg-warning/10 px-4 py-3 text-sm leading-6 text-warning-foreground" role="note">
          Реквизиты оператора и адрес для обращений должны быть настроены владельцем Benefit до ввода сервиса в эксплуатацию.
        </p>
      )}
    </section>
  )
}
