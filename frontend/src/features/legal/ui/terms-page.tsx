import { termsSections } from '@/features/legal/model/legal-documents'
import { LegalPageLayout } from '@/features/legal/ui/legal-page-layout'

export function TermsPage() {
  return (
    <LegalPageLayout
      title="Пользовательское соглашение"
      lead="Условия использования кабинета кандидата и доступных функций сервиса Benefit."
      sections={termsSections}
    />
  )
}
