# Benefit design system — stage 1

The initial UI is light-only and optimized for focused forms. The visual
language uses a cool neutral background, white surfaces, blue primary actions,
large readable headings and visible three-pixel focus rings.

Gradients are not used. Backgrounds, components and decorative elements use
solid colors only.

- Minimum interactive height: 40 px; primary actions use 44 px.
- Page content width: 1120 px; form reading width: 720 px.
- Form labels and errors are textual; color is never the only signal.
- At 360 px, cards lose decorative outer padding and actions become full width.
- Russian labels may wrap. Navigation and cards must not assume short English.
- Success appears only after the mutation response. If the confirming profile
  request fails, the UI states that the save succeeded but current data could
  not be confirmed.
- OTP cooldown text is not a live region, so the one-second countdown does not
  continuously interrupt screen-reader users.

Shared primitives contain no product or API logic. `ContactForm` belongs
to the candidate profile feature because its fields and save semantics are
defined by that domain.
