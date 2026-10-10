import { Link } from '@tanstack/react-router'
import { talentDefaults } from '@/features/talent/model/talent-search'

export function CabinetNavigation({ employer = false }: { employer?: boolean }) {
  const className = 'inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring'
  const activeProps = { className: 'bg-primary/10 text-primary' }
  return <nav aria-label="Главная навигация" className="flex flex-wrap gap-1 py-2">
    {!employer ? <Link to="/profile" search={{ section: undefined }} className={className} activeProps={activeProps}>Профиль</Link> : null}
    {employer ? <Link to="/talent" search={talentDefaults} className={className} activeProps={activeProps}>Кандидаты</Link> : null}
    <Link to="/vacancies" search={{ offset: 0 }} className={className} activeProps={activeProps}>{employer ? 'Мои вакансии' : 'Вакансии'}</Link>
    <Link to="/messages" className={className} activeProps={activeProps}>Сообщения</Link>
    {employer ? <Link to="/pipelines" className={className} activeProps={activeProps}>Пайплайны</Link> : null}
  </nav>
}
