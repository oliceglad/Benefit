import { publicationConsentSections } from '@/features/legal/model/legal-documents'
import { LegalPageLayout } from '@/features/legal/ui/legal-page-layout'

export function PublicationConsentPage() {
  return (
    <LegalPageLayout
      title="Согласие на публикацию профиля"
      lead="Условия показа профиля кандидата работодателям в сервисе Benefit."
      sections={publicationConsentSections}
    />
  )
}
