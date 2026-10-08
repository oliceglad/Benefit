import { ContactForm } from '@/features/candidate-profile/ui/contact-form'

export function ProfilePage() {
  return (
    <section className="min-w-0 space-y-6">
      <div className="space-y-2">
        <p className="text-sm font-semibold text-primary">Личный кабинет</p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Мой профиль</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
          Здесь можно изменить контактные данные.
        </p>
      </div>

      <ContactForm />
    </section>
  )
}
