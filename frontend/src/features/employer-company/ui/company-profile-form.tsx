import { zodResolver } from '@hookform/resolvers/zod'
import { Building2, Check, Globe2, Info, Mail, MapPin, RotateCcw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Controller, useForm, useWatch } from 'react-hook-form'

import {
  companyFormSchema,
  companyIndustryOptions,
  type CompanyFormValues,
} from '@/features/employer-company/model/company-form'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

export function CompanyProfileForm({ initialValues }: { initialValues: CompanyFormValues }) {
  const form = useForm<CompanyFormValues>({
    resolver: zodResolver(companyFormSchema),
    defaultValues: initialValues,
  })
  const draft = useWatch({ control: form.control, defaultValue: initialValues })
  const { errors, isSubmitted, isValid } = form.formState
  const previewName = draft.name?.trim().replace(/\s+/g, ' ') || 'Название компании'

  return (
    <div className="company-form-layout">
      <form noValidate className="min-w-0 space-y-6" onSubmit={(event) => void form.handleSubmit(() => undefined)(event)}>
        <Card id="company-details" aria-labelledby="company-details-heading">
          <CardHeader>
            <SectionHeading number="01" title="О компании" id="company-details-heading" />
            <CardDescription>Главное о вас: название, направление работы и команда.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <Field id="company-name" label="Название компании" required error={errors.name?.message}>
              <Input id="company-name" placeholder="Как называется ваша компания" autoComplete="organization" maxLength={200} aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? 'company-name-error' : undefined} {...form.register('name')} />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field id="company-industry" label="Отрасль" required error={errors.industry?.message}>
                <Controller name="industry" control={form.control} render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="company-industry" aria-invalid={Boolean(errors.industry)} aria-describedby={errors.industry ? 'company-industry-error' : undefined}>
                      <SelectValue placeholder="Выберите отрасль" />
                    </SelectTrigger>
                    <SelectContent className="company-glass-popover">
                      {companyIndustryOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )} />
              </Field>
              <Field id="company-city" label="Город" error={errors.city?.message}>
                <Input id="company-city" placeholder="Например, Самара" autoComplete="address-level2" maxLength={100} aria-invalid={Boolean(errors.city)} aria-describedby={errors.city ? 'company-city-error' : undefined} {...form.register('city')} />
              </Field>
            </div>
            <Field id="company-website" label="Сайт компании" error={errors.website?.message}>
              <Input id="company-website" type="url" inputMode="url" autoComplete="url" placeholder="https://company.ru" maxLength={300} aria-invalid={Boolean(errors.website)} aria-describedby={errors.website ? 'company-website-error' : undefined} {...form.register('website')} />
            </Field>
            <Field id="company-description" label="Описание" required error={errors.description?.message}>
              <Textarea id="company-description" className="min-h-40" placeholder="Что вы создаёте, для кого и как устроена ваша команда" maxLength={8000} aria-invalid={Boolean(errors.description)} aria-describedby={errors.description ? 'company-description-error company-description-hint' : 'company-description-hint'} {...form.register('description')} />
              <p id="company-description-hint" className="text-xs leading-5 text-muted-foreground">Расскажите о продукте и задачах, с которыми предстоит работать.</p>
            </Field>
          </CardContent>
        </Card>

        <Card id="company-contacts" aria-labelledby="company-contacts-heading">
          <CardHeader>
            <SectionHeading number="02" title="Контакты" id="company-contacts-heading" />
            <CardDescription>К кому обратиться с вопросами о вашей команде.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-5 sm:grid-cols-2">
            <Field id="company-contact-name" label="Контактное лицо" error={errors.contactName?.message}>
              <Input id="company-contact-name" autoComplete="name" placeholder="Имя и фамилия" maxLength={200} aria-invalid={Boolean(errors.contactName)} aria-describedby={errors.contactName ? 'company-contact-name-error' : undefined} {...form.register('contactName')} />
            </Field>
            <Field id="company-contact-email" label="Рабочая почта" error={errors.contactEmail?.message}>
              <Input id="company-contact-email" type="email" inputMode="email" autoComplete="email" placeholder="hr@company.ru" aria-invalid={Boolean(errors.contactEmail)} aria-describedby={errors.contactEmail ? 'company-contact-email-error' : undefined} {...form.register('contactEmail')} />
            </Field>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <div role="status" aria-live="polite">
            {isSubmitted && isValid ? (
              <p className="flex items-start gap-2 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-6">
                <Check className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
                Поля заполнены корректно. В этой пробе данные не отправляются на сервер.
              </p>
            ) : null}
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Button type="button" variant="ghost" onClick={() => form.reset(initialValues)}>
              <RotateCcw aria-hidden="true" />Вернуть пример
            </Button>
            <Button type="submit" className="sm:min-w-48">Проверить форму</Button>
          </div>
        </div>
      </form>

      <aside className="company-live-preview min-w-0 space-y-5" aria-label="Предпросмотр компании">
        <div className="company-preview-caption">
          <span>Взгляд кандидата</span><span>Предпросмотр</span>
        </div>
        <Card className="company-preview-card overflow-hidden">
          <div className="company-preview-cover px-6 py-7">
            <div className="flex items-start justify-between gap-4">
              <span className="company-avatar flex size-14 items-center justify-center rounded-2xl text-primary">
                <Building2 className="size-7" strokeWidth={1.6} aria-hidden="true" />
              </span>
              <Badge variant="secondary" className="company-card-badge">Компания</Badge>
            </div>
            <h2 className="mt-5 break-words text-2xl font-semibold leading-tight tracking-tight">{previewName}</h2>
            <p className="mt-2 text-sm leading-5 text-muted-foreground">{companyIndustryOptions.find((option) => option.value === draft.industry)?.label || 'Отрасль компании'}</p>
          </div>
          <div className="space-y-5 p-6">
            <div className="space-y-3 text-sm text-muted-foreground">
              {draft.city?.trim() ? <PreviewDetail icon={<MapPin />} value={draft.city} /> : null}
              {draft.website?.trim() ? <PreviewDetail icon={<Globe2 />} value={draft.website.replace(/^https?:\/\//, '').replace(/\/$/, '')} /> : null}
            </div>
            <p className="whitespace-pre-wrap break-words text-sm leading-6">{draft.description?.trim() || 'Здесь появится ваше описание: продукт, задачи и подход к работе.'}</p>
            {draft.contactEmail?.trim() ? (
              <div className="space-y-2 border-t pt-5">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Связаться с командой</p>
                <PreviewDetail icon={<Mail />} value={draft.contactEmail} />
                {draft.contactName?.trim() ? <p className="break-words pl-6 text-xs text-muted-foreground">{draft.contactName}</p> : null}
              </div>
            ) : null}
          </div>
        </Card>
        <div className="company-team-note">
          <Info aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold">Сначала — команда</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Кандидату проще ответить на приглашение, когда понятно, кто вы и над чем работает ваша команда.</p>
          </div>
        </div>
        <p className="px-1 text-xs leading-5 text-muted-foreground">Карточка обновляется, пока вы заполняете форму.</p>
      </aside>
    </div>
  )
}

function SectionHeading({ number, title, id }: { number: string; title: string; id: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="company-section-number flex size-8 shrink-0 items-center justify-center rounded-lg text-primary" aria-hidden="true">{number}</span>
      <CardTitle id={id}>{title}</CardTitle>
    </div>
  )
}

function Field({ id, label, required, error, children }: {
  id: string
  label: string
  required?: boolean
  error?: string
  children: ReactNode
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id}>{label}{required ? <><span className="text-muted-foreground" aria-hidden="true"> *</span><span className="sr-only"> (обязательное поле)</span></> : null}</Label>
      {children}
      {error ? <p id={`${id}-error`} role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}

function PreviewDetail({ icon, value }: { icon: ReactNode; value: string }) {
  return <p className="flex min-w-0 items-start gap-2 text-sm leading-5 text-muted-foreground"><span className="mt-0.5 shrink-0 [&_svg]:size-4" aria-hidden="true">{icon}</span><span className="min-w-0 break-words">{value}</span></p>
}
