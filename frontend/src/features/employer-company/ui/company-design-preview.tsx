import { Building2, ChevronRight, FileText, GitBranch, Mail } from 'lucide-react'
import { useEffect } from 'react'

import fspLogo from '@/features/employer-company/assets/fsp-logo.svg'
import type { CompanyFormValues } from '@/features/employer-company/model/company-form'
import { CompanyProfileForm } from '@/features/employer-company/ui/company-profile-form'
import { HiringJourneyPreview } from '@/features/employer-company/ui/hiring-journey-preview'

import './company-glass.css'

const exampleCompany: CompanyFormValues = {
  name: 'Команда Север',
  industry: 'outsource',
  description: 'Создаём веб-сервисы для бизнеса: от первых прототипов до продуктов, которыми пользуются каждый день.\n\nРаботаем небольшими командами, обсуждаем решения вместе и ценим понятный код.',
  city: 'Самара',
  website: 'https://sever.example',
  contactName: 'Анна, команда найма',
  contactEmail: 'team@sever.example',
}

export function CompanyDesignPreview() {
  useEffect(() => {
    const previousTitle = document.title
    document.title = 'Benefit — профиль компании · дизайн-проба'
    return () => { document.title = previousTitle }
  }, [])

  return (
    <div className="company-glass" id="company-profile">
      <div className="company-atmosphere" aria-hidden="true">
        <span className="company-orb company-orb-blue" />
        <span className="company-orb company-orb-deep" />
        <span className="company-orb company-orb-red" />
        <span className="company-glass-ring" />
      </div>

      <a className="company-skip-link" href="#company-main">К содержимому</a>
      <aside className="company-sidebar company-glass-panel" aria-label="Кабинет работодателя">
        <div className="company-brand">
          <img src={fspLogo} width="282" height="94" alt="ФСП — Федерация спортивного программирования" />
          <span className="company-product-name">Benefit<span aria-hidden="true"> / </span><span>для работодателей</span></span>
        </div>
        <nav aria-label="Разделы профиля" className="company-navigation">
          <p className="company-nav-caption">Рабочее пространство</p>
          <a href="#company-profile" aria-current="page" className="company-nav-active"><Building2 aria-hidden="true" /><span>Компания</span><ChevronRight aria-hidden="true" /></a>
          <a href="#company-details"><FileText aria-hidden="true" /><span>О компании</span></a>
          <a href="#company-contacts"><Mail aria-hidden="true" /><span>Контакты</span></a>
          <a href="#hiring-journey"><GitBranch aria-hidden="true" /><span>Этапы найма</span></a>
        </nav>
        <div className="company-sidebar-footer">
          <p>Кабинет<br /><span>работодателя</span></p>
        </div>
      </aside>

      <main className="company-main" id="company-main" tabIndex={-1}>
        <div className="company-topbar">
          <p className="company-breadcrumb">Кабинет работодателя<ChevronRight aria-hidden="true" /><span>Компания</span></p>
          <span className="company-preview-badge">Дизайн-проба</span>
        </div>

        <header className="company-page-heading">
          <p className="company-eyebrow">Люди. Команды. Возможности.</p>
          <h1>Профиль компании</h1>
          <p>Покажите, кто стоит за следующей большой идеей.<br className="hidden sm:block" /> Знакомство с вашей командой начинается здесь.</p>
        </header>

        <div className="company-test-notice company-glass-panel">
          <p><strong>Тестовые данные</strong><span>Редактируйте поля и проверяйте форму. Изменения действуют до обновления страницы.</span></p>
        </div>

        <CompanyProfileForm initialValues={exampleCompany} />

        <HiringJourneyPreview />

        <footer className="company-page-footer">
          <p>Benefit <span aria-hidden="true">/</span> Знакомство начинается с команды</p>
          <p>* Обязательные поля</p>
        </footer>
      </main>
    </div>
  )
}
