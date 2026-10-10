import type { PipelineDraft, PipelineStage } from '@/features/pipelines/model/pipeline-draft'
import type { BranchGraphNode, GraphBranch } from '@/shared/ui/branch-graph'

export const hiringBranches: GraphBranch[] = [
  { id: 'main', label: 'Основной маршрут', tone: 'blue' },
  { id: 'people', label: 'Знакомство с командой', tone: 'navy' },
  { id: 'technical', label: 'Техническая оценка', tone: 'red' },
]

function branchForStage(stage: PipelineStage): string {
  if (['tech_interview', 'assignment'].includes(stage.kind)) return 'technical'
  if (['hr_interview', 'team_meeting', 'final_interview'].includes(stage.kind)) return 'people'
  return 'main'
}

export function pipelineGraphNodes(pipeline: PipelineDraft): BranchGraphNode[] {
  return pipeline.stages.map((stage) => ({
    id: stage.id,
    title: stage.title || 'Без названия',
    description: stage.description,
    branchId: branchForStage(stage),
  }))
}
