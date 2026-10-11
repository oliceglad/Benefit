const LOGO_MAX_BYTES = 5 * 1024 * 1024
const logoTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])

export function validateCompanyLogo(file: File): string | null {
  if (!logoTypes.has(file.type)) return 'Выберите изображение JPEG, PNG или WebP.'
  if (file.size > LOGO_MAX_BYTES) return 'Логотип должен быть не больше 5 МБ.'
  return null
}
