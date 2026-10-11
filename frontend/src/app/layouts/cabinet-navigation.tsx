import { Link } from '@tanstack/react-router'
import { Menu } from 'lucide-react'
import { talentDefaults } from '@/features/talent/model/talent-search'

import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

const employerLinks = [
  { to: '/talent', label: 'Кандидаты', search: talentDefaults },
  { to: '/company', label: 'Компания' },
  { to: '/vacancies', label: 'Мои вакансии', search: { offset: 0 } },
  { to: '/messages', label: 'Сообщения' },
  { to: '/pipelines', label: 'Пайплайны' },
] as const

export function CabinetNavigation({ employer = false }: { employer?: boolean }) {
  const className = 'inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring'
  const activeProps = { className: 'bg-primary/10 text-primary' }
  if (employer) {
    return (
      <>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" size="icon" variant="ghost" className="xl:hidden" aria-label="Открыть навигацию">
              <Menu aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            {employerLinks.map((item) => (
              <DropdownMenuItem key={item.to} asChild>
                <Link
                  to={item.to}
                  search={'search' in item ? item.search : undefined}
                  activeProps={{ className: 'bg-primary/10 text-primary' }}
                >
                  {item.label}
                </Link>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <nav aria-label="Главная навигация" className="hidden min-w-0 items-center gap-1 xl:flex">
          {employerLinks.map((item) => (
            <Link key={item.to} to={item.to} search={'search' in item ? item.search : undefined} className={className} activeProps={activeProps}>
              {item.label}
            </Link>
          ))}
        </nav>
      </>
    )
  }
  return <nav aria-label="Главная навигация" className="flex flex-wrap gap-1 py-2">
    {!employer ? <Link to="/profile" search={{ section: undefined }} className={className} activeProps={activeProps}>Профиль</Link> : null}
    <Link to="/vacancies" search={{ offset: 0 }} className={className} activeProps={activeProps}>Вакансии</Link>
    <Link to="/messages" className={className} activeProps={activeProps}>Сообщения</Link>
  </nav>
}
