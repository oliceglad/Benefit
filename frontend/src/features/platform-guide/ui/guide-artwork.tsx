import { BadgeCheck, BriefcaseBusiness, GitBranch, ListFilter, MessageSquare, UserRound, Users } from 'lucide-react'
import { useId } from 'react'

import type { GuideStep } from '@/features/platform-guide/model/guide-steps'
import { BrandMark } from '@/shared/ui/brand-logo'

const icons = { team: Users, skills: BadgeCheck, match: ListFilter, route: GitBranch, chat: MessageSquare, profile: UserRound, vacancy: BriefcaseBusiness }

export function GuideArtwork({ step }: { step: GuideStep }) {
  const patternId = useId()
  const Icon = icons[step.icon]

  return (
    <aside className="platform-guide__art" aria-hidden="true">
      <div className="platform-guide__art-label"><BrandMark className="size-7" /><span>Люди. Команды. Возможности.</span></div>
      <div key={step.id} className="platform-guide__scene">
        <svg className="platform-guide__branches" viewBox="0 0 360 330" fill="none">
          <defs><pattern id={patternId} width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="currentColor" /></pattern></defs>
          <rect width="360" height="330" fill={`url(#${patternId})`} opacity=".12" />
          <g className="platform-guide__track" stroke="currentColor" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round">
            <path d="M60 54V280" />
            <path d="M60 68H206C274 68 274 149 206 149H60" />
            <path d="M60 181H220C291 181 291 268 220 268H60" />
          </g>
          <g className="platform-guide__nodes" fill="var(--card)" stroke="currentColor" strokeWidth="4">
            <circle cx="60" cy="68" r="8" /><circle cx="60" cy="149" r="8" /><circle cx="60" cy="181" r="8" />
            <circle cx="60" cy="268" r="8" className="platform-guide__red-node" />
          </g>
        </svg>
        {step.cards.map((label, index) => <div key={label} className={`platform-guide__art-card platform-guide__art-card--${index}`}><span className="platform-guide__art-icon"><Icon size={17} /></span><span>{label}</span></div>)}
      </div>
      <p className="platform-guide__art-caption">У каждого пути есть начало.<br /><span>Найдите своё в Benefit.</span></p>
    </aside>
  )
}
