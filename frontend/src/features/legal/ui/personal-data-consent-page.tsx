import { personalDataConsentSections } from '@/features/legal/model/legal-documents'
import { LegalPageLayout } from '@/features/legal/ui/legal-page-layout'

export function PersonalDataConsentPage() {
  return (
    <LegalPageLayout
      title="Согласие на обработку персональных данных"
      lead="Условия обработки персональных данных кандидата при использовании Benefit."
      sections={personalDataConsentSections}
    />
  )
}
