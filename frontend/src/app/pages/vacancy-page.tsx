import { VacancyPipeline } from '@/features/pipelines/ui/vacancy-pipeline'
import { VacancyDetailPage } from '@/features/vacancies/ui/vacancy-detail-page'

export function VacancyPage() {
  return <VacancyDetailPage renderPipeline={(vacancyId) => <VacancyPipeline key={vacancyId} vacancyId={vacancyId} />} />
}
