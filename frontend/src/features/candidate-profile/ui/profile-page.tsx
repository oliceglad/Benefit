import { useQuery } from '@tanstack/react-query'
import { useBlocker, useNavigate, useSearch } from '@tanstack/react-router'
import { AlertCircle, ArrowLeft, ArrowRight, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  candidateConsentsQueryKey,
  candidateProfileQueryKey,
  getCandidateConsents,
  getCandidateProfile,
  getProfileDictionaries,
  profileDictionariesQueryKey,
} from '@/features/candidate-profile/api/profile'
import { profileDraft, useProfileDraft } from '@/features/candidate-profile/model/profile-draft'
import { isProfileSectionId, nextProfileSection, profileSections, type ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import { ConsentsPublication } from '@/features/candidate-profile/ui/consents-publication'
import { JuryStepTools } from '@/features/candidate-profile/ui/jury-step-tools'
import { ContactForm } from '@/features/candidate-profile/ui/contact-form'
import { ExperienceForm } from '@/features/candidate-profile/ui/experience-form'
import { PersonalForm } from '@/features/candidate-profile/ui/personal-form'
import { PreferencesForm } from '@/features/candidate-profile/ui/preferences-form'
import { ProfileFileActions } from '@/features/candidate-profile/ui/profile-file-actions'
import { CandidateProfileOverview, ProfileSummaryCard } from '@/features/candidate-profile/ui/profile-overview'
import { SkillsForm } from '@/features/candidate-profile/ui/skills-form'
import { SpecializationForm } from '@/features/candidate-profile/ui/specialization-form'
import { UnsavedChangesDialog } from '@/features/candidate-profile/ui/unsaved-changes-dialog'
import { isApiError } from '@/shared/api/transport/api-error'
import { useDesktopLayout } from '@/shared/lib/use-desktop-layout'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Spinner } from '@/shared/ui/spinner'

export function ProfilePage() {
  const search = useSearch({ strict: false })
  const requestedSection = isProfileSectionId(search.section) ? search.section : null
  const isDesktop = useDesktopLayout()
  const section = requestedSection ?? (isDesktop ? 'personal' : null)
  const navigate = useNavigate()
  const draft = useProfileDraft()
  const skipBlock = useRef(false)
  const previousRequestedSection = useRef<ProfileSectionId | null>(requestedSection)
  const formStartRef = useRef<HTMLDivElement>(null)
  const [importActive, setImportActive] = useState(false)
  const [savingNavigation, setSavingNavigation] = useState(false)
  const [juryPending, setJuryPending] = useState(false)
  const blocker = useBlocker({
    shouldBlockFn: () => draft.isDirty && !skipBlock.current,
    enableBeforeUnload: () => draft.isDirty,
    withResolver: true,
  })
  const profile = useQuery({ queryKey: candidateProfileQueryKey, queryFn: ({ signal }) => getCandidateProfile(signal) })
  const dictionaries = useQuery({ queryKey: profileDictionariesQueryKey, queryFn: ({ signal }) => getProfileDictionaries(signal), staleTime: 5 * 60_000 })
  const consents = useQuery({ queryKey: candidateConsentsQueryKey, queryFn: ({ signal }) => getCandidateConsents(signal) })

  useEffect(() => {
    if (!isDesktop || requestedSection) return
    void navigate({ to: '/profile', search: { section: 'personal' }, replace: true })
  }, [isDesktop, navigate, requestedSection])

  useEffect(() => {
    if (!requestedSection || previousRequestedSection.current === requestedSection) return
    previousRequestedSection.current = requestedSection
    const frame = window.requestAnimationFrame(() => formStartRef.current?.scrollIntoView({ block: 'start' }))
    return () => window.cancelAnimationFrame(frame)
  }, [requestedSection])

  function navigateTo(next: ProfileSectionId, force = false): void {
    if (force) skipBlock.current = true
    void navigate({ to: '/profile', search: { section: next } }).finally(() => { skipBlock.current = false })
  }

  function navigateToOverview(force = false): void {
    if (force) skipBlock.current = true
    void navigate({ to: '/profile', search: { section: undefined } }).finally(() => { skipBlock.current = false })
  }

  async function saveAndProceed(): Promise<void> {
    setSavingNavigation(true)
    const saved = await profileDraft.save()
    setSavingNavigation(false)
    if (saved && blocker.status === 'blocked') {
      profileDraft.forceClean()
      blocker.proceed()
    }
  }

  function discardAndProceed(): void {
    profileDraft.discard()
    profileDraft.forceClean()
    if (blocker.status === 'blocked') blocker.proceed()
  }

  if (profile.isPending || dictionaries.isPending) {
    return <Card className="min-h-96"><CardContent className="grid min-h-96 place-items-center"><Spinner label="Загружаем профиль…" /></CardContent></Card>
  }

  if (profile.isError || dictionaries.isError || !profile.data || !dictionaries.data) {
    const error = profile.error ?? dictionaries.error
    return <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Профиль не загрузился</AlertTitle><AlertDescription className="space-y-3"><p>{isApiError(error) ? error.message : 'Проверьте подключение и повторите попытку.'}</p><Button type="button" size="sm" variant="outline" onClick={() => { void profile.refetch(); void dictionaries.refetch() }}><RotateCcw aria-hidden="true" />Повторить</Button></AlertDescription></Alert>
  }

  const fileActions = <ProfileFileActions key={section ?? 'overview'} profile={profile.data} dictionaries={dictionaries.data} draft={draft} onImportActiveChange={setImportActive} />

  if (!isDesktop && section === null) {
    return (
      <section className="min-w-0">
        <CandidateProfileOverview profile={profile.data} dictionaries={dictionaries.data} consents={consents.data} consentsFailed={consents.isError} resumeActions={fileActions} onNavigate={navigateTo} />
        <UnsavedChangesDialog open={blocker.status === 'blocked'} saving={savingNavigation} onSave={() => void saveAndProceed()} onDiscard={discardAndProceed} onStay={() => { if (blocker.status === 'blocked') blocker.reset() }} />
      </section>
    )
  }

  const activeSection = section ?? 'personal'
  const current = profileSections.find((item) => item.id === activeSection) ?? profileSections[0]
  const next = nextProfileSection(activeSection)
  const continueToNext = () => { if (next) navigateTo(next, true) }
  const returnAfterSave = () => navigateToOverview(true)

  return (
    <section className="min-w-0 space-y-6 max-lg:-mx-4 max-lg:min-h-svh max-lg:bg-card max-lg:px-4">
      {isDesktop ? <div inert={juryPending}><ProfileSummaryCard profile={profile.data} onNavigate={navigateTo} /></div> : null}
      {!importActive ? (
        <div ref={formStartRef} className="scroll-mt-4 space-y-6">
          <JuryStepTools section={activeSection} completed={profile.data.completeness.onboarding_completed} dirty={draft.isDirty} onPendingChange={setJuryPending} />
          <div inert={juryPending} className="grid min-w-0 gap-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:items-start">
            {isDesktop ? (
              <nav aria-label="Разделы профиля" className="sticky top-5 space-y-1.5 rounded-2xl border bg-card p-2 shadow-card">
                {profileSections.map((item) => <button key={item.id} type="button" aria-current={activeSection === item.id ? 'page' : undefined} className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-3 text-left text-sm font-medium transition-colors ${activeSection === item.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`} onClick={() => navigateTo(item.id)}>{item.shortTitle}{activeSection === item.id ? <ArrowRight className="size-4" aria-hidden="true" /> : null}</button>)}
              </nav>
            ) : (
              <header className="sticky top-0 z-30 -mx-4 flex min-w-0 items-center gap-2 border-b bg-card/96 px-4 py-2 backdrop-blur lg:static lg:mx-0 lg:border-0 lg:p-0">
                <Button type="button" variant="ghost" size="icon" className="shrink-0" aria-label="Вернуться к обзору профиля" onClick={() => navigateToOverview()}><ArrowLeft aria-hidden="true" /></Button>
                <h1 className="min-w-0 break-words text-xl font-semibold">{current.title}</h1>
              </header>
            )}
            <div className="min-w-0" key={activeSection}>
              {activeSection === 'personal' ? <PersonalForm profile={profile.data} onContinue={isDesktop ? continueToNext : returnAfterSave} standalone={!isDesktop} /> : null}
              {activeSection === 'contacts' ? <ContactForm onContinue={isDesktop ? continueToNext : returnAfterSave} standalone={!isDesktop} /> : null}
              {activeSection === 'specialization' ? <SpecializationForm profile={profile.data} dictionaries={dictionaries.data} onContinue={isDesktop ? continueToNext : returnAfterSave} standalone={!isDesktop} /> : null}
              {activeSection === 'skills' ? <SkillsForm profile={profile.data} dictionaries={dictionaries.data} onContinue={isDesktop ? continueToNext : returnAfterSave} standalone={!isDesktop} /> : null}
              {activeSection === 'experience' ? <ExperienceForm profile={profile.data} dictionaries={dictionaries.data} onContinue={isDesktop ? continueToNext : returnAfterSave} standalone={!isDesktop} /> : null}
              {activeSection === 'preferences' ? <PreferencesForm profile={profile.data} dictionaries={dictionaries.data} onContinue={isDesktop ? continueToNext : returnAfterSave} standalone={!isDesktop} /> : null}
              {activeSection === 'consents' ? <ConsentsPublication profile={profile.data} onNavigate={navigateTo} standalone={!isDesktop} /> : null}
            </div>
          </div>
        </div>
      ) : null}
      {isDesktop ? <div inert={juryPending}>{fileActions}</div> : null}
      <UnsavedChangesDialog open={blocker.status === 'blocked'} saving={savingNavigation} onSave={() => void saveAndProceed()} onDiscard={discardAndProceed} onStay={() => { if (blocker.status === 'blocked') blocker.reset() }} />
    </section>
  )
}
