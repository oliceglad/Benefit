import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

export function UnsavedChangesDialog({
  open,
  saving,
  onSave,
  onDiscard,
  onStay,
}: {
  open: boolean
  saving: boolean
  onSave: () => void
  onDiscard: () => void
  onStay: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={(next) => { if (!next && !saving) onStay() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Есть несохранённые изменения</AlertDialogTitle>
          <AlertDialogDescription>
            Сохраните раздел перед переходом или откажитесь от внесённых изменений.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={saving} onClick={onStay}>Остаться</AlertDialogCancel>
          <Button type="button" variant="outline" disabled={saving} onClick={onDiscard}>
            Не сохранять
          </Button>
          <Button type="button" disabled={saving} onClick={onSave}>
            {saving ? <Spinner label="Сохраняем…" /> : 'Сохранить'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
