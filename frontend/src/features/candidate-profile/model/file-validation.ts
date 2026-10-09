export const PHOTO_MAX_BYTES = 5 * 1024 * 1024
export const RESUME_MAX_BYTES = 10 * 1024 * 1024

const photoTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])

export function validatePhotoFile(file: File): string | null {
  if (!photoTypes.has(file.type)) return 'Выберите изображение JPEG, PNG или WebP.'
  if (file.size > PHOTO_MAX_BYTES) return 'Фото должно быть не больше 5 МБ.'
  return null
}

export function validateResumeFile(file: File): string | null {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    return 'Выберите файл в формате PDF.'
  }
  if (file.size > RESUME_MAX_BYTES) return 'PDF должен быть не больше 10 МБ.'
  return null
}
