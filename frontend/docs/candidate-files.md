# Candidate photo and resume contract

Backend revision: `388a90a221c6c8339f8513cdf1ce3227a4970c53`.

## Photo

| Operation | Request | Success | Rules |
|---|---|---|---|
| Upload or replace | `PUT /api/v1/candidates/me/photo`, multipart field `file` | `204` | JPEG, PNG or WebP, at most 5 MiB. Server applies EXIF orientation, resizes to at most 800×800, strips metadata and stores JPEG. |
| Read own photo | `GET /api/v1/candidates/me/photo` | private `image/jpeg` body | `404 photo_not_found` when absent. Fetched through authenticated transport and displayed from a revocable Blob URL. |
| Delete | `DELETE /api/v1/candidates/me/photo` | `204` | Idempotent. UI requires confirmation. |

Upload errors include `413 photo_too_large` and `422 invalid_photo`. Client-side
checks improve feedback, but the server remains authoritative.

## PDF import

`POST /api/v1/candidates/me/resume/import` receives multipart field `file`.
The PDF limit is 10 MiB. The parser reads at most 15 pages and 60,000 extracted
characters. Invalid, encrypted and image-only documents produce
`invalid_pdf`, `encrypted_pdf` or `pdf_without_text` errors.

Without the query parameter, or with `apply=false`, the response is only a
preview:

- `draft`: fields that passed `ProfileUpdate` validation;
- `warnings`: skipped or ambiguous data reported by the parser;
- `applied: false` and no profile mutation.

With `apply=true`, the server can parse the uploaded file again. Scalar values fill
only `null` or empty fields. Skills, soft skills, roles, languages and links
append non-duplicates. Experience, education, courses and projects fill only
when the corresponding current list is empty. Existing non-empty scalar and
replacement-list data is preserved. The response lists the changed top-level
keys in `applied_fields`.

The import endpoint does not support selecting individual preview fields. The
frontend therefore keeps `apply=false`, lets the candidate choose top-level
fields, validates the selected subset and sends it through the existing profile
PATCH. Selected scalar values replace their profile field; selected skills,
soft skills, roles, languages and links append non-duplicates; selected
experience, education, course and project arrays replace their respective
current array. Every replacement is labelled before confirmation.

Technical skill candidates are additionally checked against
`GET /api/v1/candidates/dictionaries/skills?q=` and only exact canonical catalog
matches remain selectable. This prevents prose fragments and punctuation from
becoming profile skills even if the current server parser included them. The
frontend rejects obvious prose before making requests, checks at most 12 unique
candidates with concurrency 2, and stops further checks when the catalog is
unavailable or rate-limited. A catalog failure leaves the resume preview usable
and omits unverified skills instead of failing the entire PDF import.
Consent records, publication state, verified grade and assessment results are
outside the selectable schema and are never imported.

The heuristic server parser detects a name only in the first three extracted
PDF lines and only when a whole line matches its name pattern. When the PDF text
layout does not satisfy that rule, the preview returns `Не удалось определить
ФИО`. The frontend has no extracted source text and does not infer a legal name
from the filename; the candidate can fill it in the personal-data form.

## PDF export

`GET /api/v1/candidates/me/resume.pdf` returns the current saved profile as
`application/pdf` with an RFC 5987 filename `resume-{last_name|candidate}.pdf`.
It is an authenticated binary request through the gateway. The client validates
both MIME type and `%PDF` signature before starting a download. Export does not
publish or otherwise mutate the profile.
