import { Link } from '@tanstack/react-router'
import { PipelinesPage } from '@/features/pipelines/ui/pipelines-page'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'

export function PipelineDesignPreview() {
  return <div className="min-h-svh"><header className="border-b bg-card"><div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-6"><BrandLogo className="h-8" /><div className="flex items-center gap-4"><span className="text-xs text-muted-foreground">Предпросмотр конструктора</span><Button asChild variant="ghost" size="sm"><Link to="/vacancies" search={{ offset: 0 }}>Вакансии</Link></Button></div></div></header><main className="mx-auto max-w-6xl px-4 py-10 sm:px-6"><PipelinesPage preview /></main></div>
}
