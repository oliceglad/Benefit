export function normalizePhone(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''
  let compact = trimmed.replace(/[\s()-]/g, '')
  if (compact.startsWith('8') && compact.length === 11) compact = `+7${compact.slice(1)}`
  return compact.startsWith('+') ? compact : `+${compact}`
}

export function formatPhone(value: string): string {
  const normalized = normalizePhone(value)
  const russian = /^\+7(\d{3})(\d{3})(\d{2})(\d{2})$/.exec(normalized)
  if (!russian) return value
  return `+7 (${russian[1]}) ${russian[2]}-${russian[3]}-${russian[4]}`
}

export function normalizeTelegram(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''
  const handle = trimmed.replace(/^(https?:\/\/)?(t\.me\/|@)/, '')
  return `@${handle}`
}

export function parseLocalizedNumber(value: string): number {
  return Number(value.trim().replace(',', '.'))
}

export function salaryDigits(value: string): string {
  return value.replace(/\s/g, '')
}

export function formatSalary(value: string): string {
  const digits = salaryDigits(value)
  if (!/^\d+$/.test(digits)) return value
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(digits))
}

export function parseSalary(value: string): number {
  return Number(salaryDigits(value))
}
