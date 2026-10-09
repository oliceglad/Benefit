export function LegalLinks() {
  return (
    <nav className="flex flex-wrap justify-center gap-x-4 gap-y-2 px-2 text-center text-xs text-muted-foreground" aria-label="Правовые документы">
      <a className="underline-offset-4 hover:text-foreground hover:underline" href="/privacy">Политика конфиденциальности</a>
      <a className="underline-offset-4 hover:text-foreground hover:underline" href="/terms">Пользовательское соглашение</a>
    </nav>
  )
}
