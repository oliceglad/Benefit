# API coverage — account, candidate profile and vacancies

Backend revision: `388a90a221c6c8339f8513cdf1ce3227a4970c53`.

| Scenario | Gateway operation | Auth | Status |
|---|---|---|---|
| Account registration | `POST /api/v1/auth/register` | Public | Implemented; candidate/employer role picker |
| Email verification | `POST /api/v1/auth/verify-email` | Public | Implemented; requests HttpOnly-cookie delivery |
| Resend verification code | `POST /api/v1/auth/resend-code` | Public | Implemented; cooldown and `Retry-After` enforced |
| Login | `POST /api/v1/auth/login` | Public | Implemented |
| Current account | `GET /api/v1/users/me` | Access cookie | Implemented; restores the session after reload |
| Refresh | `POST /api/v1/auth/refresh` | Refresh cookie + CSRF | Implemented, bodyless and single-flight |
| Logout | `POST /api/v1/auth/logout` | Refresh cookie + CSRF | Implemented; waits for an in-flight refresh |
| Own candidate profile | `GET /api/v1/candidates/me` | `candidate` | Implemented |
| Update profile sections | `PATCH /api/v1/candidates/me` | `candidate` | Implemented; section-only payloads, full replacement arrays |
| Profile dictionaries | `GET /api/v1/candidates/dictionaries` | `candidate` | Implemented; response validated with Zod |
| Skill suggestions | `GET /api/v1/candidates/dictionaries/skills?q=` | `candidate` | Implemented; debounced and cancellable |
| Consent status | `GET /api/v1/candidates/me/consents` | `candidate` | Implemented |
| Grant consent | `POST /api/v1/candidates/me/consents` | `candidate` | Implemented; explicit current-version action only |
| Revoke consent | `DELETE /api/v1/candidates/me/consents/{type}` | `candidate` | Implemented; confirmation and profile refresh |
| Publish profile | `POST /api/v1/candidates/me/publish` | `candidate` | Implemented; server completeness is authoritative |
| Unpublish profile | `POST /api/v1/candidates/me/unpublish` | `candidate` | Implemented |
| Assessment catalog | `GET /api/v1/assessments/tests` | `candidate` | Implemented |
| Assessment survey and status | `GET /api/v1/assessments/survey`, `GET /api/v1/assessments/status` | `candidate` | Implemented |
| Start and resume assessment | `POST /api/v1/assessments/attempts`, `GET /api/v1/assessments/attempts/{id}` | `candidate` | Implemented |
| Current assessment task | `GET /api/v1/assessments/attempts/{id}/current-task` | `candidate` | Implemented; opening starts the server task timer |
| Submit assessment answer | `POST /api/v1/assessments/attempts/{id}/answers` | `candidate` | Implemented |
| Finish and view result | `POST /api/v1/assessments/attempts/{id}/finish`, `GET /api/v1/assessments/attempts` | `candidate` | Implemented |
| Candidate photo | `PUT`, `GET`, `DELETE /api/v1/candidates/me/photo` | `candidate` | Implemented; private Blob URL is revoked on replacement, unmount and account change |
| Resume import preview | `POST /api/v1/candidates/me/resume/import` | `candidate` | Implemented; multipart preview does not mutate the profile |
| Apply selected resume fields | `PATCH /api/v1/candidates/me` | `candidate` | Implemented; explicit field selection, then authoritative profile GET |
| Export own resume | `GET /api/v1/candidates/me/resume.pdf` | `candidate` | Implemented; authenticated binary request, PDF signature and filename validation |

The committed schemas in `openapi/` are snapshots of the running auth and
candidate services. They include internal operations because FastAPI emits one
schema per service; browser code uses only gateway-published operations listed
above. The assessment snapshot is extracted from the assessment service at the
same backend revision. Employer assignments, assessment administration,
matching and chat are explicitly outside this slice.

## Registration contract confirmed in backend

- Registration accepts `email`, `password`, `role` and optional `full_name`.
  The frontend exposes the existing `candidate` and `employer` roles. The server remains authoritative.
- Password length is 8–128 characters and it must contain a letter and a
  digit. The current backend configuration accepts `.ru`, `.su`, `.рф` and
  explicitly allowlisted domains.
- Successful registration returns `email`, `code_expires_in` and
  `resend_available_in`. The current defaults are 600 and 60 seconds.
- Verification accepts the email and exactly six digits. Leading zeroes are
  significant. Login and verification request `X-Auth-Mode: cookie`; token
  fields in the response stay null and JavaScript retains only the current user.
- Resend deliberately returns the same accepted response for an unknown or
  already verified email. The UI does not reveal whether an account exists.

Relevant server errors:

- `401`: invalid credentials/token; protected requests may perform one
  bodyless cookie refresh and one replay.
- `403`: inactive account, unverified email or wrong role; no refresh loop.
  Only the explicit `email_not_verified` code offers the verification route.
- `422`: `error.details` entries are mapped to form fields. `service` and
  `request_id` are preserved for diagnostics.
- `429`: `Retry-After` is exposed by `ApiError` and shown to the user.

## Contract gaps

The OpenAPI schema describes request and success models, but does not enumerate
the application error codes, allowed email-domain configuration, verification
attempt limit, or `Retry-After` behavior. Those details were verified against
the handlers at the backend revision above and must be rechecked when it moves.
The UI never displays an attempts-remaining value because the API does not
return one.

## Candidate profile contract notes

`PATCH /candidates/me` distinguishes omitted values from explicit `null`.
Omitted fields are preserved; nullable scalar fields are cleared by `null`.
Every supplied array replaces the stored array in full. Detailed field and
dictionary mapping is maintained in `profile-sections.md`.

The initial 2026-10-09 audit found unavailable relative consent-document routes.
The current frontend resolves server-provided same-origin paths and provides
the `/legal/personal-data` and `/legal/publication` pages. Both documents and
manual consent acceptance were checked during the prior local candidate run.
The server still supplies the current document version and URL.

## Technical assessment contract

- A candidate starts one full assessment for a specialization and target
  grade. There is no endpoint for starting an isolated single-skill test.
- Profile skills are submitted with the survey and influence server-side task
  selection. Every task also lists the skills it covers.
- The attempt status is `in_progress`, `completed` or `expired`. Only one active
  attempt is allowed. Retry availability is controlled by server cooldowns and
  their `available_at` value.
- The overall attempt timer starts on `POST /attempts`. Loading the current task
  starts that task's own timer. The UI derives no fresh deadline and always
  renders the server `deadline_at`, `started_at` and limits.
- Supported answers are a single option, multiple options or text, matching
  `single_choice`, `multiple_choice` and `text`. The answer response says
  whether the attempt is finished; the result is read only from the server.
- The result provides an overall outcome (`not_confirmed`, `confirmed` or
  `exceeded`), an optional `confirmed_grade`, and per-skill percentages.
  Per-skill rows do not contain a confirmation flag or threshold. Consequently
  the UI shows the score as a result and describes the confirmed grade
  separately; it never invents a “skill confirmed” status.

The backend repository currently contains no committed assessment content
packs, so an environment without imported tests legitimately returns an empty
catalog. The frontend shows that state as unavailable instead of offering a
fake attempt.

## Photo and resume files

The verified upload, import, merge and export rules are recorded in
`candidate-files.md`. OpenAPI currently describes the photo and PDF download
success bodies as `void`, even though the handlers return binary data. The
frontend therefore uses the generated URL builders with the common transport
for those two GET requests and validates the returned Blob. Generated code is
not edited.

## Previously identified blockers

- The relative consent-document route blocker was resolved by the frontend
  routes described above; it is retained here as historical context.
- The dictionaries response still has no `industries` collection. The profile
  accepts an `industry` enum, but the frontend cannot offer a correctly labelled
  selector from the documented dictionary contract. This blocker remains open.

## Vacancies and pipeline constructor — 2026-10-10

The employer and application snapshots were added for the existing contracts
at repository revision `edc285a4bbf6e71d6df24b703230a7445280ab3c`.

| Scenario | Gateway operation | Auth | Status |
|---|---|---|---|
| Vacancy catalog and filters | `GET /api/v1/vacancies` | Account cookie | Implemented |
| Published vacancy | `GET /api/v1/vacancies/{id}` | Account cookie | Implemented |
| Own vacancies | `GET /api/v1/employers/vacancies` | `employer` | Implemented |
| Own vacancy | `GET /api/v1/employers/vacancies/{id}` | `employer` | Implemented |
| Create draft | `POST /api/v1/employers/vacancies` | `employer` | Implemented |
| Edit full vacancy | `PUT /api/v1/employers/vacancies/{id}` | `employer` | Implemented; existing need link preserved |
| Publish / unpublish / close | `PATCH /api/v1/employers/vacancies/{id}` | `employer` | Implemented; explicit confirmation |
| First-vacancy company setup | `GET/PUT /api/v1/employers/company` | `employer` | Implemented; only offered for missing company |
| Own applications | `GET /api/v1/applications` | `candidate` | Implemented |
| Apply to vacancy | `POST /api/v1/applications` | `candidate` | Implemented; explicit action with contact disclosure |
| Pipeline persistence | Contract pending | `employer` | Local browser drafts only; no pipeline API called |

The pipeline stage catalog is a user-requested proposal. It has no automatic
mapping to application statuses. Scope, routes, backend handoff and verification
limits are recorded in [vacancies-and-pipelines.md](vacancies-and-pipelines.md).

## Chat — 2026-10-10

Conversation list/detail, paginated history, text sending, read receipts and
attachment upload/download use the existing `/api/v1/chat` public operations.
`/api/v1/chat/ws` delivers updates with REST polling during reconnects. Both
account roles use the same feature, with server-authorized participant access.
The saved snapshot, error behavior and missing participant display names are
documented in [chat.md](chat.md). Task execution and assessment flows are unchanged.
