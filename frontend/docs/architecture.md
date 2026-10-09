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
from the future cabinet navigation. On mobile `/profile` is the overview with
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
candidate through `/users/me`; an expired access cookie causes one shared
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
