import { defineConfig } from 'orval'

const output = (target: string, schemas: string) => ({
  mode: 'single' as const,
  target,
  schemas,
  client: 'react-query' as const,
  httpClient: 'fetch' as const,
  clean: true,
  override: {
    mutator: {
      path: './src/shared/api/transport/orval-fetch.ts',
      name: 'orvalFetch',
    },
    query: {
      useQuery: true,
      useMutation: true,
      signal: true,
    },
  },
})

export default defineConfig({
  auth: {
    input: './openapi/auth.openapi.json',
    output: output(
      './src/shared/api/generated/auth/auth.ts',
      './src/shared/api/generated/auth/models',
    ),
  },
  candidates: {
    input: './openapi/candidates.openapi.json',
    output: output(
      './src/shared/api/generated/candidates/candidates.ts',
      './src/shared/api/generated/candidates/models',
    ),
  },
  assessments: {
    input: './openapi/assessments.openapi.json',
    output: output(
      './src/shared/api/generated/assessments/assessments.ts',
      './src/shared/api/generated/assessments/models',
    ),
  },
})
