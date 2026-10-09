import { privacyPolicySections } from '@/features/legal/model/legal-documents'
import { LegalPageLayout } from '@/features/legal/ui/legal-page-layout'

export function PrivacyPolicyPage() {
  return (
    <LegalPageLayout
      title="Политика конфиденциальности"
      lead="Правила обработки и защиты персональных данных пользователей сервиса подбора IT-кандидатов Benefit."
      sections={privacyPolicySections}
    />
  )
}
