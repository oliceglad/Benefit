# API coverage — candidate auth and contacts

Backend revision: `866be4955f878d55e34ecaaafafd61a984f63a25`.

| Scenario | Gateway operation | Auth | Status |
|---|---|---|---|
| Candidate registration | `POST /api/v1/auth/register` | Public | Implemented; always sends `role=candidate` |
| Email verification | `POST /api/v1/auth/verify-email` | Public | Implemented; establishes the existing in-memory session |
| Resend verification code | `POST /api/v1/auth/resend-code` | Public | Implemented; cooldown and `Retry-After` enforced |
| Login | `POST /api/v1/auth/login` | Public | Implemented |
| Current account | `GET /api/v1/users/me` | Bearer | Implemented |
| Refresh | `POST /api/v1/auth/refresh` | Refresh token body | Implemented, single-flight |
| Logout | `POST /api/v1/auth/logout` | Refresh token body | Implemented |
| Own candidate profile | `GET /api/v1/candidates/me` | `candidate` | Implemented |
| Update contacts | `PATCH /api/v1/candidates/me` | `candidate` | Implemented |

The committed schemas in `openapi/` are snapshots of the running auth and
candidate services. They include internal operations because FastAPI emits one
schema per service; browser code uses only gateway-published operations listed
above. Employer, matching and chat are explicitly outside this slice.

## Registration contract confirmed in backend

- Registration accepts `email`, `password`, `role` and optional `full_name`.
  The frontend fixes `role` to `candidate`; no role picker is exposed.
- Password length is 8–128 characters and it must contain a letter and a
  digit. The current backend configuration accepts `.ru`, `.su`, `.рф` and
  explicitly allowlisted domains.
- Successful registration returns `email`, `code_expires_in` and
  `resend_available_in`. The current defaults are 600 and 60 seconds.
- Verification accepts the email and exactly six digits. Leading zeroes are
  significant. A successful response returns the same token shape as login.
- Resend deliberately returns the same accepted response for an unknown or
  already verified email. The UI does not reveal whether an account exists.

Relevant server errors:

- `401`: invalid credentials/token; protected requests may refresh once.
- `403`: inactive account, unverified email or wrong role; no refresh loop.
  Only the explicit `email_not_verified` code offers the verification route.
- `422`: validation details mapped to form fields when locations match.
- `429`: `Retry-After` is exposed by `ApiError` and shown to the user.

## Contract gaps

The OpenAPI schema describes request and success models, but does not enumerate
the application error codes, allowed email-domain configuration, verification
attempt limit, or `Retry-After` behavior. Those details were verified against
the handlers at the backend revision above and must be rechecked when it moves.
The UI never displays an attempts-remaining value because the API does not
return one.
