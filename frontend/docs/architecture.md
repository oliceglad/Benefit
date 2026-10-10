# Frontend architecture

The production slice lets a candidate register, verify their email or sign in
through the existing gateway, edit the complete supported candidate profile by
section, manage current consents and ask the server to publish or unpublish the
profile. Every section save is confirmed with a fresh profile GET.

The browser calls same-origin paths. Vite proxies `/api` to the configurable
`BENEFIT_GATEWAY_URL`; production must provide the same paths at the frontend
origin. Components never know a backend host.

## Boundaries

`app` composes routes, providers and global policies.
`features/auth` and `features/candidate-profile` own behavior and product copy.
`shared/api`, `shared/session`, `shared/ui` and `shared/lib` contain reusable,
business-neutral infrastructure.

`app/layouts/candidate-layout.tsx` owns the reusable candidate cabinet shell:
header, account menu, session controls and page container. Feature pages render
only their section content. The account trigger shows the candidate identity on
desktop and stays avatar-sized on mobile; logout remains the same protected
session action inside its accessible dropdown.

The navigation inside `features/candidate-profile` is deliberately separate
from the cabinet navigation. On mobile `/profile` is the overview with
server-derived section summaries, photo controls and resume actions. A section
uses `/profile?section=<id>` and becomes a focused edit screen with a back
action. On desktop the same section URL renders inside the existing sidebar
layout; entering `/profile` selects the first section without requiring the
mobile overview. TanStack Router scroll restoration returns the overview to its
previous position. Browser Back/Forward and direct section links therefore work
without a second local navigation state. A feature-local draft
coordinator protects route changes, reload/close and logout. Draft values stay
inside React Hook Form and are never persisted in browser storage.

Candidate profile forms send only their own PATCH keys. Array editors send the
complete current value because the backend replaces JSON arrays. TanStack
Query owns server state and server-provided completeness; forms are reset from
fresh data only while clean, so background refreshes cannot overwrite typing.
The skill search uses the query text in its cache key and forwards AbortSignal,
which prevents a late response for an older query from becoming current UI.

Photo and resume flows stay inside `features/candidate-profile`. Private photo
and PDF responses are fetched through the same cookie/CSRF transport as JSON;
tokens never enter image URLs. Blob URLs are tracked centrally and revoked on
replacement, component cleanup, logout and authenticated account change.
Photo selection is previewed locally before an explicit upload.

Resume import first sends one multipart request with the default `apply=false`
and renders the returned draft alongside the current profile without changing
it. The candidate explicitly selects top-level fields; the frontend validates
that subset and saves it through the existing profile PATCH, then refreshes
profile and completeness. Recognised technical skills are kept only when an
exact canonical match exists in the server skill catalog. The PDF and parsed
personal data are never persisted in browser storage. While the import review
is active, section forms are unmounted so a conflicting save cannot run. Export
downloads the last server-saved profile and never publishes it.

Technical assessment remains a candidate-profile subflow rather than a new
cabinet section. A skill card links to the shared specialization/grade test,
and its presentation state is built in a feature-local view model. The model
keeps profile draft state, assessment availability, active attempts, results
and the overall confirmed grade distinct. The attempt page reads timing and
results from the assessment service, so reload resumes the same attempt and
never restarts a browser-owned timer.

The generated clients depend on one Fetch mutator. It sends cookie credentials,
requests HttpOnly-cookie delivery for authentication operations, adds the
double-submit CSRF header to state-changing requests, maps the shared backend
error envelope to `ApiError`, preserves cancellation and coordinates one
refresh request for concurrent 401 responses. A request is replayed once only.
Refresh completion is revision-guarded. Logout first closes the local session,
waits for an in-flight refresh, and then revokes the final refresh cookie, so a
late response cannot restore the session. Private Query data and tracked Blob
URLs are cleared when the session becomes anonymous, is being re-established
or changes to another authenticated user.

Registration and verification state belongs to `features/auth`. Only the
email, resend deadline and code expiry are retained in memory while the tab is
open. Passwords and verification codes are never put in the URL, logs or
persistent browser storage. If the page is reloaded, the verification screen
accepts the email again so the user can continue with the code from the letter.

## Session decision

The browser uses the backend cookie mode. `benefit_access` and
`benefit_refresh` are HttpOnly and never enter JavaScript or persistent browser
storage. The readable `benefit_csrf` cookie is copied into `X-CSRF-Token` for
POST, PUT, PATCH and DELETE requests. On reload the router restores the current
account through `/users/me`; an expired access cookie causes one shared
bodyless refresh and one replay. Development stays same-origin through the
Vite `/api` proxy.

## Routing decision

The application uses TanStack Router with an explicit code-defined route tree.
Route declarations remain isolated in `src/app/router.tsx`; profile subsection
state is validated there and exposed as optional `?section=` without adding a
second route tree. The absent parameter means mobile overview; a present value
addresses one of the seven profile sections. Layout changes at the `lg`
breakpoint do not mount duplicate forms, so current React Hook Form state is
preserved while resizing.
Assessment conditions live at `/assessments`; an active attempt has the stable
route `/assessments/attempts/$attemptId`, which makes refresh and Back/Forward
safe without putting answers or other personal data in the URL.

Public legal documents live outside the authenticated route at `/privacy` and
`/terms`; authentication screens link to both. Consent documents live at the
relative same-origin routes `/legal/personal-data` and `/legal/publication`
returned by candidate-service. The frontend resolves those server-provided
paths and never substitutes a local document when the backend omits one.
Their visible operator details
come from `VITE_LEGAL_OPERATOR_NAME`, `VITE_LEGAL_OPERATOR_ADDRESS` and
`VITE_LEGAL_CONTACT_EMAIL`. Deployments must set these values before production.
The document version is aligned with the current candidate-consent version, but
the pages do not grant consent or replace the document URL returned by the
candidate-service.

## Vacancies and pipeline composition

`app/layouts/cabinet-layout.tsx` selects the existing candidate shell or the
employer shell. The shared cabinet navigation belongs to `app`, while feature
pages own only their content. Auth accepts the existing candidate and employer
roles; candidate profile routes and employer pipeline routes remain guarded.

`features/vacancies` owns the catalog, owner list, filters, detail, apply,
create/edit and publication behavior. Its first-vacancy company setup only
collects the required API fields when no company exists. Full vacancy data and
the existing need link are preserved on edit. `?q`, `city`, `grade`,
`work_format`, `salary_min`, employer `status` and `offset` are
validated at the route. New vacancy and pipeline pages load lazily.

`features/pipelines` owns a frontend constructor with an explicit local-draft
model. It uses the generated employer client only to read own vacancy options.
The pipeline draft contains stage configuration, not candidate records, and
is stored under an account-specific versioned browser key. Persistence to the
server has no custom-template contract; no hiring mutation endpoint is called.
Main now contains a separate `/api/v1/hiring` process/interview/offer API that
will need explicit frontend integration rather than an implicit stage mapping.
The DEV-only preview composes the same page with a separate local key and
disables employer API reads. Its authenticated DEV session may read the public
vacancy catalog to attach a local preview. See `vacancies-and-pipelines.md` for
scope and the proposed stage catalog.

The candidate-facing pipeline is composed into vacancy detail by
`app/pages/vacancy-page.tsx` through a render prop. Feature modules do not import
each other's private files. `shared/ui/branch-graph` owns the API-independent
SVG rail, branch nodes and single-stage inline expansion through the existing
Radix Collapsible primitive. Stage lobes echo the Benefit logo and use common
primary/border/card tokens; there is no separate detail panel. `features/pipelines`
owns stage grouping and local preview data. DEV snapshots are attached explicitly
per vacancy and update across tabs. Production never treats them as published
server configuration or candidate progress.

## Chat

`features/chat` owns the two-role `/messages` workspace and nested conversation
route. The parent remains mounted when choosing another conversation, preserving
in-memory drafts without browser storage. The generated chat client uses the
shared authenticated transport; a Blob option supports arbitrary file downloads.
The socket invalidates account-scoped queries and REST polling covers reconnects.
UI states and current API limitations are recorded in [chat.md](chat.md).

## Candidate bank

`features/talent` owns employer search and inline public candidate details.
`app` composes the guarded lazy `/talent` route and the employer navigation link.
Filters, sort, offset and selected candidate ID are validated URL state.
The selected ID is excluded from the request/cache parameters, so opening a card
does not refetch the search or discard an unsent filter draft. Query keys include
the current account ID; logout still clears private query data centrally.

The generated matching client uses existing transport and cancellation.
Feature-local presentation schemas parse untyped skill/achievement dictionaries;
achievement links permit only HTTP(S). The UI uses server categories and grade
confirmation, never converts declared skills into confirmed qualifications,
and fetches no private contacts. See [talent.md](talent.md).

The same `/talent` workspace now owns need selection, inline creation/editing,
status changes and explainable matching. `app/pages/talent-page` composes the
existing vacancy company prerequisite/setup with the talent feature; neither
feature imports the other's private modules. Their generic field wrapper lives
in `shared/ui/form-field` and carries no business rules.

Need and match queries include account and need IDs. Match keys additionally
include the saved revision, offset and hide-contacted flag. Successful mutations
replace the saved requirements with the authoritative response, invalidate
matching and clear the selected candidate/page. Catalog filter drafts are not
silently mixed into need matching: the server endpoint accepts only pagination
and hide-contacted. Need ID and expanded candidate survive reload through URL
state. Generated generic response dictionaries are checked by a feature-local
Zod schema before rendering. Dirty form state is subscribed during render and
used by both local cancel confirmation and the router blocker.

## Optional platform guide

`features/platform-guide` owns a role-specific, manually launched introduction.
The employer and candidate layouts compose `BrandGuide` in place of the static
header logo. Clicking it opens the existing Radix menu; only its explicit guide
item mounts the native modal dialog. There is no automatic launch or persisted
completion state and no dependency on profile onboarding or generated APIs.
The underlying route stays mounted, preserving unsaved forms and search state.
CSS/SVG animations respect reduced motion; keyboard focus is contained in the
dialog and restored to the trigger on close. See [platform-guide.md](platform-guide.md).

## Invitations and company composition

`app/pages/messages-page` injects the invitation inbox into the existing chat
workspace; `app/pages/talent-page` supplies candidate action slots for both catalog
and matching. `app/pages/vacancies-page` adds the company panel to the existing
vacancies section. These features use generated clients and the shared transport,
without cross-feature private imports. See [invitations.md](invitations.md).
