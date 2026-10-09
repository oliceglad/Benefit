import { describe, expect, it } from 'vitest'

import { resolveDocumentUrl } from '@/features/candidate-profile/model/legal-document-url'

describe('resolveDocumentUrl', () => {
  it('resolves the relative document paths returned by candidate-service', () => {
    expect(resolveDocumentUrl('/legal/personal-data', 'https://benefit.example')).toBe('https://benefit.example/legal/personal-data')
    expect(resolveDocumentUrl('/legal/publication', 'https://benefit.example')).toBe('https://benefit.example/legal/publication')
  })

  it('rejects executable and malformed document URLs', () => {
    expect(resolveDocumentUrl('javascript:alert(1)', 'https://benefit.example')).toBeNull()
    expect(resolveDocumentUrl('://broken', 'https://benefit.example')).toBeNull()
    expect(resolveDocumentUrl('//untrusted.example/document', 'https://benefit.example')).toBeNull()
  })
})
