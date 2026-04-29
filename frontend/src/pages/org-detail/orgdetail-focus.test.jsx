import React, { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { createRoot } from 'react-dom/client'

import OrgDetail from '../OrgDetail.jsx'
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const turnstileSiteKeyMock = vi.hoisted(() => vi.fn(() => ''))

vi.mock('../../components/UpgradeCallout', () => ({
  default: () => React.createElement('div', null, 'upgrade'),
}))

vi.mock('@marsidev/react-turnstile', () => ({
  Turnstile: React.forwardRef(function MockTurnstile(_props, ref) {
    React.useImperativeHandle(ref, () => ({ reset: vi.fn() }))
    return React.createElement('div', { 'data-testid': 'turnstile-widget' })
  }),
}))

vi.mock('../../components/RichTextEditor', () => ({
  default: ({ value, onChange, placeholder }) =>
    React.createElement('textarea', {
      'aria-label': placeholder,
      value,
      onChange: (event) => onChange(event.target.value),
    }),
}))

vi.mock('../../components/LanguageSwitcher', () => ({
  default: () => React.createElement('div', null, 'language-switcher'),
}))

vi.mock('../../components/NotificationBell', () => ({
  default: () => React.createElement('div', null, 'notification-bell'),
}))

import { orgClient } from '../../lib/organisations'

vi.mock('../../lib/organisations', () => ({
  orgClient: {
    getOrg: vi.fn(),
    listDocuments: vi.fn(),
    listMyOrgs: vi.fn(),
    getOrgStats: vi.fn(),
    listMembers: vi.fn(),
    listInvitations: vi.fn(),
    inviteMember: vi.fn(),
    createDocument: vi.fn(),
  }
}))

vi.mock('../../lib/auth', () => ({
  authHeaders: () => ({ Authorization: 'Bearer test-token' }),
}))

vi.mock('../../lib/documentImport', () => ({
  extractDocxFile: vi.fn(),
  extractPdfFile: vi.fn(),
}))

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (key) => key }),
}))

vi.mock('../../lib/turnstile', () => ({
  getTurnstileSiteKey: turnstileSiteKeyMock,
}))

vi.mock('../../store/authStore', () => ({
  default: (selector) => selector({ user: { id: 'user-1', email: 'owner@example.com' } }),
}))

// Wait explicitly imported at the top

function buttonByText(container, text) {
  return Array.from(container.querySelectorAll('button')).find((button) =>
    button.textContent?.includes(text),
  )
}

async function flush() {
  await act(async () => {
    await Promise.resolve()
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

async function waitFor(check, message) {
  const deadline = Date.now() + 5000
  while (Date.now() < deadline) {
    if (check()) return
    await flush()
  }
  throw new Error(message)
}

describe('OrgDetail inline forms focus behavior', () => {
  let container
  let root

  beforeEach(() => {
    vi.restoreAllMocks()
    turnstileSiteKeyMock.mockReturnValue('')

    container = document.createElement('div')
    document.body.innerHTML = ''
    document.body.appendChild(container)
    root = createRoot(container)

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ orgs: [] }),
    })

    window.requestAnimationFrame = (callback) => setTimeout(() => callback(Date.now()), 0)
    window.cancelAnimationFrame = (id) => clearTimeout(id)
    HTMLElement.prototype.scrollIntoView = vi.fn()

    orgClient.getOrg.mockResolvedValue({ slug: 'acme', name: 'Acme', plan: 'team' })
    orgClient.listDocuments.mockResolvedValue({
      items: [{ id: 'doc-1', title: 'Board agenda', status: 'draft', created_at: '2025-04-03T10:00:00Z' }],
      total: 1,
    })
    orgClient.listMyOrgs.mockResolvedValue([{ slug: 'acme', role: 'owner' }])
    orgClient.getOrgStats.mockResolvedValue({
      active_docs: 1,
      pending_amendments: 0,
      member_count: 1,
    })
    orgClient.listMembers.mockResolvedValue([
      {
        id: 'user-1',
        email: 'owner@example.com',
        full_name: 'Owner Example',
        role: 'owner',
      },
    ])
    orgClient.listInvitations.mockResolvedValue([])
    orgClient.inviteMember.mockResolvedValue({})
    orgClient.createDocument.mockResolvedValue({ id: 'doc-2' })
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
  })

  it('autofocuses and restores focus for the create document inline form', async () => {
    await act(async () => {
      root.render(
        React.createElement(
          MemoryRouter,
          {
            initialEntries: ['/orgs/acme'],
            future: { v7_startTransition: true, v7_relativeSplatPath: true },
          },
          React.createElement(
            Routes,
            null,
            React.createElement(Route, {
              path: '/orgs/:slug',
              element: React.createElement(OrgDetail),
            }),
          ),
        ),
      )
    })

    await waitFor(() => !!buttonByText(container, 'org.new_document'), 'new document button not rendered')

    const trigger = buttonByText(container, 'org.new_document')
    trigger.focus()
    await act(async () => {
      trigger.click()
    })

    await waitFor(
      () => container.querySelector('input[placeholder="org.doc_title_placeholder"]') === document.activeElement,
      'create form title input did not receive focus',
    )

    const titleInput = container.querySelector('input[placeholder="org.doc_title_placeholder"]')
    await act(async () => {
      titleInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })

    await waitFor(
      () => !container.querySelector('input[placeholder="org.doc_title_placeholder"]'),
      'create form did not close on Escape',
    )
    await waitFor(
      () => document.activeElement === buttonByText(container, 'org.new_document'),
      'focus was not restored to the create trigger',
    )
  })

  it('autofocuses and restores focus for the invite member inline form', async () => {
    await act(async () => {
      root.render(
        React.createElement(
          MemoryRouter,
          {
            initialEntries: ['/orgs/acme'],
            future: { v7_startTransition: true, v7_relativeSplatPath: true },
          },
          React.createElement(
            Routes,
            null,
            React.createElement(Route, {
              path: '/orgs/:slug',
              element: React.createElement(OrgDetail),
            }),
          ),
        ),
      )
    })

    await waitFor(() => !!buttonByText(container, 'org.tab_members'), 'members tab not rendered')

    await act(async () => {
      buttonByText(container, 'org.tab_members').click()
    })

    await waitFor(() => !!buttonByText(container, 'org.invite_member'), 'invite member button not rendered')

    const trigger = buttonByText(container, 'org.invite_member')
    trigger.focus()
    await act(async () => {
      trigger.click()
    })

    await waitFor(
      () => container.querySelector('input[placeholder="org.email_placeholder"]') === document.activeElement,
      'invite form email input did not receive focus',
    )

    const emailInput = container.querySelector('input[placeholder="org.email_placeholder"]')
    await act(async () => {
      emailInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })

    await waitFor(
      () => !container.querySelector('input[placeholder="org.email_placeholder"]'),
      'invite form did not close on Escape',
    )
    await waitFor(
      () => document.activeElement === buttonByText(container, 'org.invite_member'),
      'focus was not restored to the invite trigger',
    )
  })

  it('submits invite creation without a Turnstile token when the widget is unavailable', async () => {
    turnstileSiteKeyMock.mockReturnValue('site-key')

    await act(async () => {
      root.render(
        React.createElement(
          MemoryRouter,
          {
            initialEntries: ['/orgs/acme'],
            future: { v7_startTransition: true, v7_relativeSplatPath: true },
          },
          React.createElement(
            Routes,
            null,
            React.createElement(Route, {
              path: '/orgs/:slug',
              element: React.createElement(OrgDetail),
            }),
          ),
        ),
      )
    })

    await waitFor(() => !!buttonByText(container, 'org.tab_members'), 'members tab not rendered')

    await act(async () => {
      buttonByText(container, 'org.tab_members').click()
    })

    await waitFor(() => !!buttonByText(container, 'org.invite_member'), 'invite member button not rendered')

    await act(async () => {
      buttonByText(container, 'org.invite_member').click()
    })

    await waitFor(
      () => !!container.querySelector('input[placeholder="org.email_placeholder"]'),
      'invite form email input not rendered',
    )

    const emailInput = container.querySelector('input[placeholder="org.email_placeholder"]')
    await act(async () => {
      const setNativeValue = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value',
      ).set
      setNativeValue.call(emailInput, 'new-member@example.com')
      emailInput.dispatchEvent(new Event('input', { bubbles: true }))
    })

    await act(async () => {
      buttonByText(container, 'org.send_invitation').click()
    })

    await waitFor(
      () => orgClient.inviteMember.mock.calls.length > 0,
      'inviteMember was not called',
    )
    expect(orgClient.inviteMember).toHaveBeenCalledWith('acme', 'new-member@example.com', null)
  })
})
