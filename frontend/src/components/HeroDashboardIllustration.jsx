import React, { useState } from 'react';
import { useTranslation } from '../hooks/useTranslation';
import { 
  LayoutDashboard, 
  FileText, 
  GitBranch, 
  MessageSquare, 
  CreditCard, 
  Mail, 
  Settings, 
  Search, 
  ChevronRight,
  Send,
  MoreVertical,
  CheckCircle2,
  Clock,
  CheckCircle,
  FileEdit
} from 'lucide-react';

export default function HeroDashboardIllustration() {
  const [activeTab, setActiveTab] = useState('track_changes');
  const { t } = useTranslation();

  return (
    <div className="flex w-full h-[600px] bg-[#f8fafc] text-slate-900 font-sans overflow-hidden rounded-2xl select-none">
      
      {/* Barre latérale gauche */}
      <aside className="w-64 bg-[#0f172a] text-slate-300 flex flex-col shrink-0">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-white">A</div>
          <span className="text-xl font-bold text-white">Amendly</span>
        </div>

        <nav className="flex-1 px-4 space-y-1 mt-4">
          <NavItem icon={<LayoutDashboard size={20} />} label={t('dashboard_mockup.nav_dashboard')} active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
          <NavItem icon={<FileText size={20} />} label={t('dashboard_mockup.nav_documents')} active={activeTab === 'documents'} onClick={() => setActiveTab('documents')} />
          <NavItem icon={<GitBranch size={20} />} label={t('dashboard_mockup.nav_track_changes')} hasNotification active={activeTab === 'track_changes'} onClick={() => setActiveTab('track_changes')} />
          <NavItem icon={<MessageSquare size={20} />} label={t('dashboard_mockup.nav_comments')} active={activeTab === 'comments'} onClick={() => setActiveTab('comments')} />
          <NavItem icon={<CreditCard size={20} />} label={t('dashboard_mockup.nav_pricing')} active={activeTab === 'pricing'} onClick={() => setActiveTab('pricing')} />
          <NavItem icon={<Mail size={20} />} label={t('dashboard_mockup.nav_contact')} active={activeTab === 'contact'} onClick={() => setActiveTab('contact')} />
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-1">
          <NavItem icon={<FileText size={18} />} label={t('dashboard_mockup.nav_recent_project')} small />
          <NavItem icon={<Settings size={18} />} label={t('dashboard_mockup.nav_settings')} small />
        </div>
      </aside>

      {/* Zone de contenu principale */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#f8fafc]">
        {activeTab === 'dashboard' && <DashboardView t={t} />}
        {activeTab === 'documents' && <DocumentsView t={t} />}
        {activeTab === 'track_changes' && <TrackChangesView t={t} />}
        {['comments', 'pricing', 'contact'].includes(activeTab) && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-400">
            <LayoutDashboard size={48} className="mb-4 opacity-20" />
            <p className="text-sm font-medium">Coming soon / Simulated view</p>
          </div>
        )}
      </main>
    </div>
  );
}

// ------ NOUVELLES VUES ------

const DashboardView = ({ t }) => (
  <div className="flex-1 flex flex-col p-8 overflow-y-auto custom-scrollbar">
    <div className="flex justify-between items-center mb-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">{t('dashboard_mockup.nav_dashboard')}</h1>
        <p className="text-sm text-slate-500 mt-1">Welcome back. Here is what is happening today.</p>
      </div>
      <button className="bg-blue-600 text-white px-5 py-2 rounded-lg font-medium text-sm flex items-center">
        <span>+ New Project</span>
      </button>
    </div>
    
    <div className="grid grid-cols-3 gap-6 mb-8">
      {[
        { title: 'Active Projects', value: 12, icon: <FileEdit size={24} className="text-blue-500" />, bg: 'bg-blue-50' },
        { title: 'Pending Reviews', value: 4, icon: <Clock size={24} className="text-amber-500" />, bg: 'bg-amber-50' },
        { title: 'Approved Changes', value: 38, icon: <CheckCircle size={24} className="text-emerald-500" />, bg: 'bg-emerald-50' }
      ].map((stat) => (
        <div key={stat.title} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${stat.bg}`}>
            {stat.icon}
          </div>
          <div className="flex flex-col">
            <span className="text-2xl font-bold text-slate-800">{stat.value}</span>
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{stat.title}</span>
          </div>
        </div>
      ))}
    </div>

    <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex-1 p-6 flex flex-col">
      <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-6">Recent Activity</h3>
      <div className="space-y-0">
        {[1, 2, 3].map(i => (
          <div key={i} className="flex items-center gap-4 py-4 border-b border-slate-100 last:border-0">
            <div className="w-10 h-10 bg-slate-50 border border-slate-100 rounded-lg flex items-center justify-center text-slate-400 shrink-0">
              <FileText size={18} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-800">Bylaws Amendment Draft v{i}</p>
              <p className="text-xs text-slate-500 mt-0.5">Updated {i * 2} hours ago by Emma</p>
            </div>
            <div className="px-3 py-1 bg-blue-50 text-blue-700 text-[10px] font-bold uppercase tracking-wider rounded-md">
              In Review
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

const DocumentsView = ({ t }) => (
  <div className="flex-1 flex flex-col p-8 overflow-y-auto custom-scrollbar">
    <div className="flex justify-between items-center mb-8">
      <h1 className="text-2xl font-bold text-slate-800">{t('dashboard_mockup.nav_documents')}</h1>
      <div className="flex items-center bg-white border border-slate-200 rounded-lg px-4 py-2 text-sm text-slate-400">
        <Search size={16} className="mr-2 text-slate-400" />
        <span>Search documents...</span>
      </div>
    </div>
    
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex-1">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase tracking-wider">
            <th className="p-4 font-bold">Document Name</th>
            <th className="p-4 font-bold">Status</th>
            <th className="p-4 font-bold">Last Modified</th>
            <th className="p-4 font-bold text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="text-sm text-slate-700">
          {[
            { name: 'General Assembly Rules', status: 'In Review', date: 'Oct 20, 2025', color: 'blue' },
            { name: 'Membership Policy v3', status: 'Draft', date: 'Oct 15, 2025', color: 'slate' },
            { name: 'Code of Conduct', status: 'Approved', date: 'Oct 12, 2025', color: 'emerald' },
            { name: 'Annual Report 2025', status: 'Draft', date: 'Oct 05, 2025', color: 'slate' }
          ].map((doc) => (
            <tr key={doc.name} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
              <td className="p-4 font-medium flex items-center gap-3">
                <FileText size={18} className="text-blue-600" />
                {doc.name}
              </td>
              <td className="p-4">
                <span className={`px-2 py-1 flex w-max items-center justify-center rounded-md text-[10px] font-bold uppercase tracking-wider bg-${doc.color}-50 text-${doc.color}-700`}>
                  {doc.status}
                </span>
              </td>
              <td className="p-4 text-slate-500">{doc.date}</td>
              <td className="p-4 text-right text-slate-400">
                <MoreVertical size={16} className="inline-block cursor-pointer hover:text-slate-600" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const TrackChangesView = ({ t }) => (
  <div className="flex-1 flex flex-col h-full overflow-hidden">
    {/* En-tête avec barre de progression */}
    <header className="bg-white border-b border-slate-200 px-8 py-4 shrink-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold">{t('dashboard_mockup.header_title')}</h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center bg-slate-100 rounded-full px-4 py-1.5 text-sm text-slate-600">
            <Search size={16} className="mr-2" />
            <span>{t('dashboard_mockup.header_search')}</span>
          </div>
          <button className="bg-blue-600 text-white px-5 py-2 rounded-lg font-medium text-sm flex items-center">
            <span>{t('dashboard_mockup.header_export')}</span>
            <ChevronRight size={16} className="ml-1" />
          </button>
        </div>
      </div>

      {/* Stepper (Progression) */}
      <div className="flex items-center justify-center max-w-2xl mx-auto py-2">
        <Step label={t('dashboard_mockup.step_track_changes')} status="complete" />
        <StepLine active />
        <Step label={t('dashboard_mockup.step_review')} status="active" />
        <StepLine />
        <Step label={t('dashboard_mockup.step_consolidate')} status="pending" />
        <StepLine />
        <Step label={t('dashboard_mockup.step_finalize')} status="pending" />
        <StepLine />
        <Step label={t('dashboard_mockup.step_export')} status="pending" />
      </div>
    </header>

    {/* Corps du dashboard (Document + Sidebar droite) */}
    <div className="flex-1 flex overflow-hidden">
      
      {/* Visualiseur de Document */}
      <section className="flex-1 overflow-y-auto bg-slate-100 p-8 flex justify-center custom-scrollbar">
        <div className="w-full max-w-3xl bg-white shadow-xl shadow-slate-200/50 rounded-lg p-12 min-h-[1000px]">
          <h2 className="text-2xl font-bold mb-8 text-slate-800">{t('dashboard_mockup.doc_title')}</h2>
          
          <div className="space-y-6 text-slate-600 leading-relaxed text-sm">
            <p>
              {t('dashboard_mockup.doc_p1')}
              <span className="bg-red-50 text-red-700 line-through px-1 rounded mx-1">{t('dashboard_mockup.doc_deleted_text')}</span>
              <span className="bg-red-100 text-red-800 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ml-1">{t('dashboard_mockup.badge_deleted')}</span>
              {t('dashboard_mockup.doc_p1_end')}
            </p>

            <div className="relative group">
              <p>
                {t('dashboard_mockup.doc_p2_start')} <span className="bg-red-50 text-red-700 line-through px-1 rounded">{t('dashboard_mockup.doc_p2_deleted')}</span>
                {t('dashboard_mockup.doc_p2_mid')}
                <span className="bg-green-50 text-green-700 px-1 rounded mx-1 underline decoration-green-300">{t('dashboard_mockup.doc_p2_added')}</span>
                <span className="bg-green-100 text-green-800 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ml-1">{t('dashboard_mockup.badge_added')}</span>
              </p>
              <div className="absolute -right-4 top-0 h-full w-1 bg-green-400 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"></div>
            </div>

            <p>
              {t('dashboard_mockup.doc_p3_1')}
              <span className="bg-blue-50 text-blue-700 px-1 rounded cursor-pointer border-b border-blue-200">{t('dashboard_mockup.doc_p3_2')}</span>
              {t('dashboard_mockup.doc_p3_3')}
            </p>

            <p className="text-slate-400">
              {t('dashboard_mockup.doc_p4')}
            </p>
          </div>
        </div>
      </section>

      {/* Sidebar droite (Activité/Track changes) */}
      <aside className="w-80 bg-white border-l border-slate-200 flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-100 flex justify-between items-center">
          <h3 className="font-bold text-slate-800">{t('dashboard_mockup.sidebar_title')}</h3>
          <button className="text-slate-400 hover:text-slate-600"><MoreVertical size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          <ActivityItem 
            user="Alex" 
            time="10:42 AM" 
            type={t('dashboard_mockup.activity_1_type')}
            content={t('dashboard_mockup.activity_1_content')}
          />

          <div className="space-y-3">
            <ActivityItem 
              user="Emma" 
              time="1h" 
              type={t('dashboard_mockup.activity_2_type')}
              content={t('dashboard_mockup.activity_2_content')}
            />
            <div className="ml-8 border-l-2 border-slate-100 pl-4 py-1">
              <input 
                type="text" 
                placeholder={t('dashboard_mockup.input_placeholder')}
                className="w-full text-sm bg-slate-50 border border-slate-200 rounded-md px-3 py-2 outline-none focus:border-blue-400 transition-colors"
              />
            </div>
          </div>

          <ActivityItem 
            user="David" 
            time="2h" 
            type={t('dashboard_mockup.activity_3_type')}
            content={t('dashboard_mockup.activity_3_content')}
          />
        </div>

        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <div className="relative">
            <input 
              type="text" 
              placeholder={t('dashboard_mockup.input_placeholder')}
              className="w-full bg-white border border-slate-200 rounded-lg px-4 py-3 pr-10 text-sm shadow-sm focus:ring-2 focus:ring-blue-100 outline-none"
            />
            <button className="absolute right-3 top-1/2 -translate-y-1/2 text-blue-600 hover:text-blue-700">
              <Send size={18} />
            </button>
          </div>
        </div>
      </aside>
    </div>
  </div>
);


// ------ COMPOSANTS UTILITAIRES ------

const NavItem = ({ icon, label, active = false, hasNotification = false, small = false, onClick }) => (
  <a href="#" onClick={(e) => { e.preventDefault(); if (onClick) onClick(); }} className={`
    flex items-center gap-3 px-3 py-2 rounded-lg transition-all
    ${active ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}
    ${small ? 'text-xs' : 'text-sm font-medium'}
  `}>
    <span className={active ? 'text-white' : 'text-slate-500'}>{icon}</span>
    <span className="flex-1 truncate">{label}</span>
    {hasNotification && <div className="w-2 h-2 bg-red-500 shadow-sm rounded-full"></div>}
  </a>
);

const Step = ({ label, status }) => {
  const isActive = status === 'active';
  const isComplete = status === 'complete';

  return (
    <div className="flex flex-col items-center group cursor-pointer">
      <div className={`
        w-5 h-5 rounded-full flex items-center justify-center mb-1 transition-all
        ${isComplete ? 'bg-blue-600 text-white' : isActive ? 'bg-blue-100 border-2 border-blue-600 text-blue-600' : 'bg-slate-100 text-slate-300'}
      `}>
        {isComplete ? <CheckCircle2 size={12} /> : <div className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-blue-600' : 'bg-slate-300'}`}></div>}
      </div>
      <span className={`text-[10px] whitespace-nowrap font-bold uppercase tracking-tighter ${isActive || isComplete ? 'text-slate-900' : 'text-slate-400'}`}>
        {label}
      </span>
    </div>
  );
};

const StepLine = ({ active = false }) => (
  <div className={`h-[2px] w-4 lg:w-8 mx-1 rounded-full ${active ? 'bg-blue-600' : 'bg-slate-200'}`}></div>
);

const ActivityItem = ({ user, time, type, content }) => (
  <div className="group">
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center text-[10px] font-bold">
          {user.charAt(0)}
        </div>
        <span className="text-xs font-bold text-slate-800">{user}</span>
        <span className="text-[10px] text-slate-400 font-medium">{time}</span>
      </div>
      <button className="opacity-0 group-hover:opacity-100 transition-opacity"><MoreVertical size={14} className="text-slate-300" /></button>
    </div>
    <div className="bg-slate-50 border border-slate-100 rounded-lg p-3">
      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{type}</p>
      <p className="text-xs text-slate-600 leading-relaxed">{content}</p>
    </div>
  </div>
);
