import { describe, expect, it } from 'vitest'

import {
  PHOTO_MAX_BYTES,
  RESUME_MAX_BYTES,
  validatePhotoFile,
  validateResumeFile,
} from './file-validation'

function fileOfSize(name: string, type: string, size: number): File {
  return new File([new Uint8Array(size)], name, { type })
}

describe('candidate file validation', () => {
  it('accepts supported photos and rejects unsupported or oversized files', () => {
    expect(validatePhotoFile(fileOfSize('photo.webp', 'image/webp', 128))).toBeNull()
    expect(validatePhotoFile(fileOfSize('photo.gif', 'image/gif', 128))).toContain('JPEG, PNG или WebP')
    expect(validatePhotoFile(fileOfSize('photo.jpg', 'image/jpeg', PHOTO_MAX_BYTES + 1))).toContain('5 МБ')
  })

  it('accepts a PDF by MIME type or extension and enforces the server limit', () => {
    expect(validateResumeFile(fileOfSize('resume.pdf', 'application/pdf', 128))).toBeNull()
    expect(validateResumeFile(fileOfSize('resume.PDF', '', 128))).toBeNull()
    expect(validateResumeFile(fileOfSize('resume.docx', 'application/octet-stream', 128))).toContain('PDF')
    expect(validateResumeFile(fileOfSize('resume.pdf', 'application/pdf', RESUME_MAX_BYTES + 1))).toContain('10 МБ')
  })
})
