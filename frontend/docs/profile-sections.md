# Candidate profile sections

Backend revision: `388a90a221c6c8339f8513cdf1ce3227a4970c53`.

| Раздел | Поля | Источник значений | Правила сохранения |
|---|---|---|---|
| Личные данные | `last_name`, `first_name`, `middle_name`, `birth_date`, `city`, `relocation_ready` | Ввод пользователя; дата ISO `YYYY-MM-DD` | PATCH только перечисленных полей. Пустые nullable-строки и дата передаются как `null`; `relocation_ready` всегда передаётся явно. |
| Контакты | `phone`, `contact_email`, `telegram`, `links` | Ввод пользователя; типы ссылок из dictionaries | Контакты нормализует сервер. `links` при передаче заменяется целиком. Почта аккаунта в этот раздел не входит. |
| Специализация | `headline`, `about`, `grade`, `roles` | `grades` и `roles` из dictionaries | `roles` заменяется целиком, максимум 5. Подтверждённые `verified_grade` и `verified_specialization` только отображаются. `industry` пока не редактируется: backend не возвращает отрасли в dictionaries. |
| Навыки | `skills`, `soft_skills`, `languages` | Hard skills — серверный поиск; уровни, soft skills и языки — dictionaries; результат проверки — assessment-service | Все три массива заменяются целиком. Hard skill отправляется каноническим именем из ответа поиска, а не свободным текстом. Дубликаты блокируются без учёта регистра. Проверка доступна только сохранённым навыкам и подтверждает общий грейд специализации, а не редактируемую самооценку. |
| Опыт и образование | `experience`, `education`, `courses`, `projects` | Ввод пользователя; уровень образования из dictionaries | Каждый переданный массив заменяется целиком. Месячные даты нормализуются сервером до первого дня месяца. Текущая работа — `end_date: null`. Записи не имеют серверных ID, поэтому редактируются по позиции в локальной форме. |
| Пожелания к работе | `salary_from`, `salary_currency`, `employment_types`, `work_formats`, `job_search_status`, `privacy` | Все перечисления, кроме валюты, из dictionaries; backend по умолчанию использует `RUB` | Массивы заменяются целиком. Валюта не выбирается: API не публикует валютный справочник. FSP achievements только отображаются. |
| Согласия и публикация | consent endpoints, `publish`, `unpublish` | Тип, заголовок, URL и требуемая версия приходят с сервера | Согласия выдаются только явной кнопкой и с текущей серверной версией. Отзыв может снять профиль с публикации. Статус и completeness после действий перечитываются с сервера. |

На мобильном `/profile` показывает обзор: краткие описания разделов строятся из
реального профиля и справочников, а серверный `completeness.percent` не
пересчитывается клиентом. Каждый раздел адресуется параметром `?section=` и
открывается как отдельный экран. На десктопе тот же URL показывает форму рядом
с боковой навигацией.

Фото управляется компактным меню возле аватара на обзоре/верхней карточке, но
хранится отдельным бинарным ресурсом и не входит в PATCH профиля. Импорт и
экспорт резюме — общие действия над профилем, поэтому на мобильном находятся в
группе «Резюме» обзора, а на десктопе — после области редактирования. Они не
дублируются внутри форм.

## PATCH semantics

`ProfileUpdate` uses `exclude_unset=True`: an omitted property is unchanged.
Nullable scalar properties may be cleared with `null`. Lists are stored as
JSON and a supplied list replaces the complete previous list. Therefore every
section mutation contains only that section's keys, while every array editor
sends the full current array for that field.

## Publication requirements

The server is authoritative. Its current required completeness checks are:
`last_name`, `first_name`, one of the contact fields, `headline`, `grade`, at
least one `role`, at least one `skill`, at least one item among experience,
projects or education, and all current consents. A 100% completeness value and
published status remain separate states.

## Contract limitations

- Dictionaries are returned by OpenAPI as an untyped object, so the frontend
  validates the response at runtime with Zod.
- `industry` is writable and has an enum in OpenAPI, but the dictionaries
  endpoint does not expose display labels. The field is not shown until the
  server publishes that dictionary.
- Consent document URLs are server configuration. An empty or invalid URL is
  shown as a blocking contract limitation; the frontend does not invent text.
- Experience, education, courses and projects have no stable record IDs. The
  frontend must send a complete replacement array for each edited collection.
- Assessment-service returns a per-skill percentage but no per-skill
  confirmation flag or passing threshold. The UI does not infer one. The only
  confirmed value is the overall grade returned by the server.
