import { CompanyPanel } from '@/features/employer-company/ui/company-panel'
import { VacanciesPage as VacanciesWorkspace } from '@/features/vacancies/ui/vacancies-page'

export function VacanciesPage() {
  return <VacanciesWorkspace companyPanel={<CompanyPanel />} />
}
