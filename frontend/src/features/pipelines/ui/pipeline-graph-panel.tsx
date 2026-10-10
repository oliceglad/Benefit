import type { PipelineDraft } from '@/features/pipelines/model/pipeline-draft'
import { hiringBranches, pipelineGraphNodes } from '@/features/pipelines/model/pipeline-graph'
import { BranchGraph } from '@/shared/ui/branch-graph'

export function PipelineGraphPanel({ pipeline, label, note }: { pipeline: PipelineDraft; label: string; note: string }) {
  return (
    <section aria-label="Пайплайн найма" className="rounded-xl border bg-card p-6 shadow-card">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-xl">
          <h2 className="text-xl font-semibold tracking-tight">Этапы найма</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">Все этапы видны до отклика. Нажмите на этап, чтобы раскрыть описание.</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="text-xs text-muted-foreground">{label}</span>
          <span className="text-xs text-muted-foreground">Этапов: {pipeline.stages.length}</span>
        </div>
      </header>
      <BranchGraph
        nodes={pipelineGraphNodes(pipeline)}
        branches={hiringBranches}
        ariaLabel="Все этапы приёма на работу"
        itemLabel="Этап"
        emptyDescription="Работодатель пока не добавил описание этого этапа."
      />
      <p className="mt-5 border-t pt-4 text-xs leading-5 text-muted-foreground">{note}</p>
    </section>
  )
}
