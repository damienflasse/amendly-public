import { Link } from 'react-router-dom'
import UpgradeCallout from '../../components/UpgradeCallout'
import { getDocumentUpgradeCallout } from './utils'

export function OrgDetailHero({
  org,
  stats,
  notificationsMuted,
  pendingToast,
  t,
  onPendingStatClick,
}) {
  return (
    <div className="mb-12 flex items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {org?.name}
          </h1>
          {notificationsMuted && (
            <Link
              to="/account"
              title={t('org.notifications_muted_badge_link')}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-highest text-on-surface font-body text-label-sm tracking-[0.02em] hover:bg-surface-container-high transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 shrink-0" aria-hidden="true">
                <path d="M10 2a6 6 0 0 0-6 6v3.586l-.707.707A1 1 0 0 0 4 14h12a1 1 0 0 0 .707-1.707L16 11.586V8a6 6 0 0 0-6-6ZM10 18a3 3 0 0 1-2.83-2h5.66A3 3 0 0 1 10 18Z" />
                <line x1="3" y1="3" x2="17" y2="17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {t('org.notifications_muted_badge')}
            </Link>
          )}
        </div>
        <p className="mt-2 font-body text-body-md text-outline">
          amendly.eu/{org?.slug}
        </p>
        {stats && (
          <>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary-fixed text-on-primary-fixed font-body text-label-sm tracking-[0.02em]">
                <span aria-hidden="true">📄</span>
                {t('org.stats_active_docs').replace('{n}', stats.active_docs)}
              </span>
              <button
                type="button"
                onClick={onPendingStatClick}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-on-surface font-body text-label-sm tracking-[0.02em] hover:bg-surface-container transition-colors"
              >
                <span aria-hidden="true">✏️</span>
                {t('org.stats_pending_amendments').replace('{n}', stats.pending_amendments)}
              </button>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-on-surface font-body text-label-sm tracking-[0.02em]">
                <span aria-hidden="true">👥</span>
                {t('org.stats_members').replace('{n}', stats.member_count)}
              </span>
            </div>
            {pendingToast && (
              <p className="mt-2 font-body text-label-sm text-outline">
                {t('org.stats_no_pending_docs')}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export function OrgDetailTabs({ activeTab, t, onChange }) {
  return (
    <div className="mt-10 mb-8 flex items-center gap-1 border-b border-surface-container-highest">
      {[
        { id: 'documents', label: t('org.tab_documents') },
        { id: 'members', label: t('org.tab_members') },
      ].map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`px-4 py-2.5 font-body text-body-md rounded-t-md transition-colors ${
            activeTab === id
              ? 'text-amendly-blue border-b-2 border-amendly-blue -mb-px font-semibold'
              : 'text-outline hover:text-on-surface'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export function MembersTabSection({
  canManage,
  showInviteForm,
  slug,
  userRole,
  orgPlan,
  currentUserId,
  inviteFormTriggerRef,
  InviteMemberForm,
  MembersPanel,
  navigate,
  setShowInviteForm,
  setStats,
  restoreTriggerFocus,
  t,
}) {
  return (
    <>
      {showInviteForm && (
        <InviteMemberForm
          slug={slug}
          userRole={userRole}
          onCancel={() => {
            setShowInviteForm(false)
            restoreTriggerFocus(inviteFormTriggerRef)
          }}
          t={t}
        />
      )}

      {!showInviteForm && canManage && (
        <div className="flex justify-end mb-6">
          <button
            ref={inviteFormTriggerRef}
            type="button"
            onClick={() => setShowInviteForm(true)}
            className="px-6 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors"
          >
            {t('org.invite_member')}
          </button>
        </div>
      )}

      <MembersPanel
        slug={slug}
        userRole={userRole}
        orgPlan={orgPlan}
        currentUserId={currentUserId}
        alwaysOpen={true}
        onMemberRemoved={() =>
          setStats((state) =>
            state ? { ...state, member_count: Math.max(0, state.member_count - 1) } : state
          )
        }
        onSelfLeft={() => navigate('/dashboard')}
        t={t}
      />
    </>
  )
}

export function DocumentsTabSection({
  documents,
  filteredDocuments,
  totalPages,
  userRole,
  canManage,
  showCreateForm,
  selectionMode,
  selectedDocIds,
  showSoloDocumentUpgrade,
  slug,
  page,
  search,
  sortBy,
  createFormTriggerRef,
  docRowRefs,
  CreateDocumentForm,
  DocumentRow,
  navigate,
  onCreateDocument,
  onShowCreateForm,
  onCancelCreate,
  onSearchChange,
  onSortChange,
  onToggleSelectionMode,
  onSelectAll,
  onOpenDeleteModal,
  onExitSelectionMode,
  onToggleDocSelection,
  onPrevPage,
  onNextPage,
  t,
}) {
  return (
    <>
      {showSoloDocumentUpgrade && (
        <div className="mb-10">
          <UpgradeCallout {...getDocumentUpgradeCallout({ t, userRole, slug })} />
        </div>
      )}

      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
            {t('org.documents_section')}
            {documents.length > 0 && (
              <span className="ml-2 font-body text-body-md text-outline">({filteredDocuments.length})</span>
            )}
          </h2>
          <div className="flex items-center gap-2">
            {userRole === 'owner' && documents.length > 0 && !showCreateForm && (
              selectionMode ? (
                <>
                  <button
                    type="button"
                    onClick={onSelectAll}
                    className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors"
                  >
                    {selectedDocIds.size === filteredDocuments.length
                      ? t('org.deselect_all')
                      : t('org.select_all')}
                  </button>
                  {selectedDocIds.size > 0 && (
                    <button
                      type="button"
                      onClick={onOpenDeleteModal}
                      className="px-4 py-2 bg-on-error-container text-white rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
                    >
                      {t('org.delete_selected').replace('{n}', selectedDocIds.size)}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={onExitSelectionMode}
                    className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors"
                  >
                    {t('org.cancel_selection')}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={onToggleSelectionMode}
                  className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors"
                >
                  {t('org.select_documents')}
                </button>
              )
            )}

            {!showCreateForm && canManage && !selectionMode && !showSoloDocumentUpgrade && (
              <button
                ref={createFormTriggerRef}
                type="button"
                onClick={onShowCreateForm}
                className="inline-flex items-center gap-2 rounded-lg bg-amendly-blue px-4 py-2.5 font-body text-body-md font-semibold text-white transition-colors hover:bg-secondary focus:outline-none focus:ring-2 focus:ring-amendly-blue"
              >
                <span aria-hidden="true">+</span>
                {t('org.new_document')}
              </button>
            )}
          </div>
        </div>

        {documents.length > 0 && (
          <div className="flex flex-col sm:flex-row gap-3 mb-6">
            <input
              type="search"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder={t('org.doc_search_placeholder')}
              className="flex-1 bg-surface-container-low rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
            />
            <div className="flex items-center gap-2 shrink-0">
              <span className="font-body text-label-sm text-outline tracking-[0.02em] whitespace-nowrap">
                {t('org.doc_sort_by')}
              </span>
              <select
                value={sortBy}
                onChange={(event) => onSortChange(event.target.value)}
                aria-label={t('org.doc_sort_label')}
                className="bg-surface-container-low rounded-md px-4 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary"
              >
                <option value="newest">{t('org.doc_sort_newest')}</option>
                <option value="oldest">{t('org.doc_sort_oldest')}</option>
                <option value="title_az">{t('org.doc_sort_title_az')}</option>
                <option value="title_za">{t('org.doc_sort_title_za')}</option>
                <option value="status">{t('org.doc_sort_status')}</option>
              </select>
            </div>
          </div>
        )}

        {filteredDocuments.length > 0 ? (
          <div className="space-y-4">
            {filteredDocuments.map((doc) => (
              <div key={doc.id} ref={(element) => { docRowRefs.current[doc.id] = element }}>
                <DocumentRow
                  doc={doc}
                  onClick={() => navigate(`/orgs/${slug}/documents/${doc.id}`)}
                  t={t}
                  selectionMode={selectionMode}
                  selected={selectedDocIds.has(doc.id)}
                  onToggle={onToggleDocSelection}
                />
              </div>
            ))}
          </div>
        ) : (
          !showCreateForm && (
            <div className="bg-surface-container-low rounded-md p-12 text-center">
              <p className="font-body text-body-md text-outline mb-8">
                {search.trim() ? t('org.no_docs_search') : t('org.no_documents')}
              </p>
              {!search.trim() && canManage && !showSoloDocumentUpgrade && (
                <button
                  ref={createFormTriggerRef}
                  type="button"
                  onClick={onShowCreateForm}
                  className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md"
                >
                  {t('org.create_first_document')}
                </button>
              )}
            </div>
          )
        )}

        {showCreateForm && (
          <CreateDocumentForm
            slug={slug}
            userRole={userRole}
            onCreated={onCreateDocument}
            onCancel={onCancelCreate}
            t={t}
          />
        )}

        {totalPages > 1 && (
          <div className="flex items-center gap-4 mt-8 justify-center">
            <button
              type="button"
              disabled={page === 1}
              onClick={onPrevPage}
              className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md disabled:opacity-40"
            >
              {t('org.previous')}
            </button>
            <span className="font-body text-body-md text-outline">
              {t('org.page_of').replace('{page}', page).replace('{total}', totalPages)}
            </span>
            <button
              type="button"
              disabled={page === totalPages}
              onClick={onNextPage}
              className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md disabled:opacity-40"
            >
              {t('org.next')}
            </button>
          </div>
        )}
      </section>
    </>
  )
}
