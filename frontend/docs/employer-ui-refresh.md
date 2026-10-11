# Обновление интерфейса кабинета работодателя

## Карта источников

| Элемент Benefit | Источник | Адаптация |
|---|---|---|
| Одноярусная навигация и мобильное меню | `shadcn-admin/src/components/layout/top-nav.tsx`, MIT | Сохранены только responsive-паттерн и dropdown; маршруты, роли и TanStack search принадлежат Benefit. |
| Меню работодателя | `shadcn-admin/src/components/layout/nav-user.tsx`, MIT | Удалены аватар донора, billing и уведомления; оставлены реальные данные сессии, роль и logout. |
| Компактный заголовок, строки и empty state вакансий | `applicant-tracking/apps/applicant-tracking/src/components/PageHeader.tsx`, `pages/JobsPage.tsx`, MIT | Русский текст, серверные статусы Benefit, URL-фильтры и реальные счётчики. |
| Раскрытие одного этапа и библиотека | `applicant-tracking/apps/applicant-tracking/src/components/StageEditorDialog.tsx`, MIT | Локальный черновик Benefit, один раскрытый этап, dropdown библиотеки, кнопки перемещения и подтверждение удаления. |
| Поля, Select, Textarea, dropdown и подтверждения | существующие `src/shared/ui/*` | Общие Benefit-токены без новой UI-библиотеки и без точечных CSS overrides. |
| Чат | существующие `src/features/chat/ui/*` | Сохранены API, WebSocket/polling, черновики, файлы и read-only; изменена только композиция и тексты состояний. |

Репозитории `shadcn-admin` и `zite/applicant-tracking` используют MIT. Точные
ревизии и пути зарегистрированы в `component-sources.yaml`. Runtime-импортов,
симлинков и зависимостей от `ui-reference` нет.

## Контрактные ограничения

- `GET /api/v1/employers/vacancies` возвращает полный список без серверных
  параметров фильтрации и пагинации, поэтому employer-фильтры применяются к
  полному серверному ответу, а страницы формируются на клиенте.
- В chat `ConversationResponse` нет имени и фотографии кандидата, поэтому
  работодатель видит короткий ID. Нет и ID вакансии для deep link.
- Пайплайны — локальные account-scoped черновики. Серверного CRUD и публикации
  кандидатам нет; предпросмотр вакансии доступен только в DEV и в этом браузере.
- У компании нет подключённых контрактов логотипа и команды, поэтому таких
  элементов в форме нет. `PUT company` не предоставляет version/ETag.
