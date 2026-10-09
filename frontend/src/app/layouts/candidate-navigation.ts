export type CandidateBackDestination = 'assessments' | 'skills'

export type CandidateBackLink = {
  destination: CandidateBackDestination
  label: string
}

export function candidateBackLink(pathname: string): CandidateBackLink | null {
  if (pathname.startsWith('/assessments/attempts/')) {
    return { destination: 'assessments', label: 'К проверкам' }
  }
  if (pathname === '/assessments' || pathname === '/assessments/') {
    return { destination: 'skills', label: 'К навыкам профиля' }
  }
  return null
}
