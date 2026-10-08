# Frontend architecture

The production slice lets a candidate register, verify their email or sign in
through the existing gateway, read their own profile, edit contacts, save them
and confirm the persisted values with a fresh GET.

The browser calls same-origin paths. Vite proxies `/api` to the configurable
`BENEFIT_GATEWAY_URL`; production must provide the same paths at the frontend
origin. Components never know a backend host.

## Boundaries

`app` composes routes, providers and global policies.
`features/auth` and `features/candidate-profile` own behavior and product copy.
`shared/api`, `shared/session`, `shared/ui` and `shared/lib` contain reusable,
business-neutral infrastructure.

`app/layouts/candidate-layout.tsx` owns the reusable candidate cabinet shell:
header, session controls and page container. Feature pages render only their
section content. When a second real section appears, desktop sidebar and mobile
drawer navigation can be added to this layout without changing profile logic.

The generated clients depend on one Fetch mutator. It adds Bearer credentials,
maps server errors to `ApiError`, preserves cancellation and coordinates one
refresh request for concurrent 401 responses. A request is replayed once only.
Refresh completion is revision-guarded: logout or a newer login cannot be
overwritten by a late response. Private Query data is cleared whenever the
session loses its tokens.

Registration and verification state belongs to `features/auth`. Only the
email, resend deadline and code expiry are retained in memory while the tab is
open. Passwords and verification codes are never put in the URL, logs or
persistent browser storage. If the page is reloaded, the verification screen
accepts the email again so the user can continue with the code from the letter.

## Session decision

Tokens are held in memory. This matches the existing JSON-token backend without
pretending JavaScript storage is an HttpOnly cookie. Reloading the page requires
login. A production-persistent session requires a backend/BFF cookie contract
and is deliberately outside this stage.

## Routing decision

The application uses TanStack Router with an explicit code-defined route tree.
For two routes this is smaller and easier to audit than generated file routing.
Route declarations remain isolated in `src/app/router.tsx`; migration to file
routing would not change feature or shared boundaries.
