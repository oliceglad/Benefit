import { ChevronDown } from 'lucide-react'
import { useId, useState, type CSSProperties } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/ui/collapsible'

import './branch-graph.css'

export type GraphBranch = {
  id: string
  label: string
  tone: 'blue' | 'navy' | 'red'
}

export type BranchGraphNode = {
  id: string
  title: string
  description: string
  branchId: string
}

type BranchGraphProps = {
  nodes: BranchGraphNode[]
  branches: GraphBranch[]
  ariaLabel: string
  itemLabel: string
  emptyDescription: string
}

// Input order is authoritative. Branch lanes group stages, not optional paths or progress.
export function BranchGraph({ nodes, branches, ariaLabel, itemLabel, emptyDescription }: BranchGraphProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const instanceId = useId()
  if (nodes.length === 0 || branches.length === 0) return null

  const branchIndex = (node: BranchGraphNode) => Math.max(0, branches.findIndex((branch) => branch.id === node.branchId))
  const railWidth = 12 + branches.length * 24
  const mainIndices = nodes.flatMap((node, index) => branchIndex(node) === 0 ? [index] : [])
  const mainStart = mainIndices[0]
  const mainEnd = mainIndices.at(-1)

  return (
    <div className="branch-graph" style={{ '--graph-rail': `${railWidth}px` } as CSSProperties}>
      <div className="branch-graph-legend" aria-label="Ветки графа">
        {branches.map((branch) => <span key={branch.id} className={`branch-graph-legend-item graph-tone-${branch.tone}`}><span aria-hidden="true" />{branch.label}</span>)}
      </div>
      <ol aria-label={ariaLabel} className="branch-graph-list">
        {nodes.map((node, index) => {
          const lane = branchIndex(node)
          const branch = branches[lane]
          const previous = nodes[index - 1]
          const previousBranch = previous ? branches[branchIndex(previous)] : branch
          const x = 16 + lane * 24
          const previousX = previous ? 16 + branchIndex(previous) * 24 : x
          const incomingTone = lane === 0 ? previousBranch.tone : branch.tone
          const hasMain = mainStart != null && mainEnd != null && mainStart !== mainEnd && index >= mainStart && index <= mainEnd
          const hasNext = index < nodes.length - 1
          const triggerId = `${instanceId}-stage-${node.id}`

          return (
            <Collapsible key={node.id} asChild open={expandedId === node.id} onOpenChange={(open) => setExpandedId(open ? node.id : null)}>
              <li className={`branch-graph-row graph-tone-${branch.tone}`}>
                <h3>
                  <CollapsibleTrigger asChild>
                    <button id={triggerId} type="button" className="branch-graph-node" aria-label={`${itemLabel} ${index + 1}: ${node.title}`}>
                      <span className="branch-graph-rail" aria-hidden="true">
                        <svg viewBox={`0 0 ${railWidth} 64`} preserveAspectRatio="none" focusable="false">
                          {hasMain ? <path className="branch-graph-trunk" d={`M16 ${index === mainStart ? 32 : 0} V${index === mainEnd ? 32 : 64}`} /> : null}
                          {previous ? <path className={`branch-graph-edge graph-tone-${incomingTone}`} d={`M${previousX} 0 C${previousX} 20 ${x} 12 ${x} 32`} /> : null}
                          {hasNext ? <path className="branch-graph-edge" d={`M${x} 32 V64`} /> : null}
                        </svg>
                        <span className="branch-graph-dot" style={{ left: x }}><span /></span>
                      </span>
                      <span className="branch-graph-node-number">{String(index + 1).padStart(2, '0')}</span>
                      <span className="branch-graph-node-title">{node.title}</span>
                      <ChevronDown className="branch-graph-chevron" size={17} aria-hidden="true" />
                    </button>
                  </CollapsibleTrigger>
                </h3>
                <CollapsibleContent className="branch-graph-expansion">
                  {/* Continue rails through the variable-height description, without stretching header curves. */}
                  {hasNext ? <span className="branch-graph-expanded-rail" style={{ left: x }} aria-hidden="true" /> : null}
                  {hasMain && index !== mainEnd && lane !== 0 ? <span className="branch-graph-expanded-trunk" aria-hidden="true" /> : null}
                  <div className="branch-graph-description" role="region" aria-labelledby={triggerId}>
                    <p>{node.description.trim() || emptyDescription}</p>
                  </div>
                </CollapsibleContent>
              </li>
            </Collapsible>
          )
        })}
      </ol>
    </div>
  )
}
