# Company design canary

Scope: one editable company screen for reviewing Benefit layout, typography,
form controls, validation and the live company-card preview. It uses the existing
UI primitives with a locally scoped FSP Liquid Glass theme. No new dependencies
are required; other application screens keep their existing theme.

## Visual direction and supplied assets

The reference image informs the sidebar, page hierarchy and two-column layout.
The company form remains the scope of this canary; invitation workflows are not
part of it. Section links navigate to the existing form sections.

Source: user-supplied `Фирменный стиль ФСП.zip`, general brand guide, pages 8,
21 and 22. Palette: primary `#402FFF`, digital accent `#0A006B`, red `#EC1D35`,
graphite `#1B1C21`, white `#EDEDED`, logo silver `#C8C9CA`. Transparent tints and
neutral shades support readable form controls. Validation uses a darker red for
contrast. No gradients are used.

Assets in `src/features/employer-company/assets/` are extracted unchanged from:

- `ЛОГО ФСП/Кирилица/Полноцвет/Для светлого фона/SVG/Лого цвет сокращенный.svg`.
- `ФИРМЕНЫЕ ШРИФТЫ ФСП/ОСНОВНОЙ JetBrains_Mono.zip`: variable upright font and OFL.
- `ФИРМЕНЫЕ ШРИФТЫ ФСП/АКЦЕНТНЫЙ TDAText.zip`: regular font, license and copyright.

The official logo is not recolored or redrawn. JetBrains Mono is the primary UI
font; TDA Text appears only in section numbers and the small decorative code mark.
Fonts are self-hosted; no external font service is contacted.

Glass surfaces use translucent solid fills, backdrop blur, white rims and soft
shadows over stationary brand-colored shapes. Text and controls retain contrast.
An opaque fallback supports missing backdrop filters and reduced transparency;
forced-colors mode keeps visible boundaries. No animation is introduced.

## Preview behavior

Run `pnpm dev` from `frontend/` and open `/preview/company` at the address printed
by Vite. The route is registered only when `import.meta.env.DEV` is true; it is
absent from the production route tree. Existing authentication is unchanged.

The example company and `.example` contacts are explicitly labelled as test
data. Edits live only in React Hook Form memory. The action checks form fields;
it neither persists data nor claims that a company was saved or verified.
The reset action restores the example.

The form covers a subset of `CompanyIn`: name, industry, description, city,
website, contact name and email. Industry labels are copied from the existing
`backend/libs/benefit-common/benefit_common/dictionaries.py` for visual review.
Before API integration, replace this snapshot with an agreed employer dictionary
contract and add the remaining company fields as needed.

After design feedback, integrate the screen into the role-protected employer
cabinet using the existing cookie/CSRF transport and an Orval-generated client.
Do not promote the preview route into a public editing endpoint.
