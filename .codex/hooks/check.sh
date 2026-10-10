#!/usr/bin/env bash
input=$(cat)
[ "$(jq -r '.stop_hook_active' <<<"$input")" = "true" ] && exit 0

# Запустите ваши тесты (по умолчанию npm test)
if ! out=$(npm test 2>&1); then
  jq -n --arg log "$(tail -n 40 <<<"$out")" \
  '{decision: "block", reason: ("Тесты не проходят. Исправь их перед завершением.\n" + $log)}'
fi
exit 0
