// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({
  publicJsonFetch: vi.fn(),
}))

import { publicJsonFetch } from './api'
import { getPublicDocument, submitPublicAmendment } from './contribute'

afterEach(() => {
  vi.clearAllMocks()
})

describe('public contribution client', () => {
  it('loads the public document without cookie auth requirements', async () => {
    publicJsonFetch.mockResolvedValueOnce({ id: 'doc-1' })

    await getPublicDocument('token-123')

    expect(publicJsonFetch).toHaveBeenCalledWith('/api/contribute/token-123')
  })

  it('submits anonymous amendments through the public endpoint', async () => {
    publicJsonFetch.mockResolvedValueOnce({ id: 'amendment-1' })
    const payload = {
      amendment_type: 'general_comment',
      justification: 'Public input',
      contributor_name: 'Alice',
    }

    await submitPublicAmendment('token-123', payload)

    expect(publicJsonFetch).toHaveBeenCalledWith('/api/contribute/token-123', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  })
})
