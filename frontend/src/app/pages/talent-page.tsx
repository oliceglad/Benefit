import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { TalentPage as TalentWorkspace } from '@/features/talent/ui/talent-page'
import { InvitationAction } from '@/features/invitations/ui/invitation-action'
import { getVacancyCompany } from '@/features/vacancies/api/vacancy-company'
import { VacancyCompanySetup } from '@/features/vacancies/ui/vacancy-company-setup'
import { RequestError } from '@/shared/api/ui/request-error'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

export function TalentPage() {
  return <TalentWorkspace prepareNewNeed={(form, onCancel) => <NeedCompanyGate onCancel={onCancel}>{form}</NeedCompanyGate>} candidateActions={(candidate, need) => <InvitationAction candidateId={candidate.user_id} name={candidate.full_name || 'кандидата'} defaults={need ? { title: need.title, salaryFrom: need.currency === 'RUB' ? need.salary_from?.toString() ?? '' : '', salaryTo: need.currency === 'RUB' ? need.salary_to?.toString() ?? '' : '', workFormat: need.work_formats?.[0] ?? '', city: need.city ?? '' } : undefined} />} />
}

function NeedCompanyGate({ children, onCancel }: { children: ReactNode; onCancel: () => void }) {
  const company = useQuery({ queryKey: ['vacancy-company'], queryFn: ({ signal }) => getVacancyCompany(signal) })
  if (company.isPending) return <Spinner label="Проверяем сведения о компании…" />
  if (company.isError) return <div className="space-y-4"><RequestError error={company.error} onRetry={() => { void company.refetch() }} /><Button variant="outline" onClick={onCancel}>Отмена</Button></div>
  if (company.data === null) return <VacancyCompanySetup purpose="need" onCancel={onCancel} />
  return children
}
