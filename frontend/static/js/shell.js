const FlowDeskShell = (() => {
  const dashboardUrl = '/static/pages/dashboard.html';
  const loginUrl = '/static/login.html';
  const liveHandlers = {};

  const navByRole = {
    submitter: [
      ['dashboard', 'Dashboard', '/static/pages/dashboard.html', 'ti-layout-dashboard'],
      ['new-request', 'New request', '/static/pages/new-request.html', 'ti-file-plus'],
      ['workflows', 'My workflows', '/static/pages/workflows.html', 'ti-files'],
    ],
    approver: [
      ['dashboard', 'Dashboard', '/static/pages/dashboard.html', 'ti-layout-dashboard'],
      ['approvals', 'Approvals', '/static/pages/approvals.html', 'ti-check'],
    ],
    admin: [
      ['dashboard', 'Dashboard', '/static/pages/dashboard.html', 'ti-layout-dashboard'],
      ['admin-users', 'Users', '/static/pages/admin-users.html', 'ti-users'],
      ['admin-config', 'Workflow config', '/static/pages/admin-config.html', 'ti-settings'],
      ['analytics', 'Analytics', '/static/pages/analytics.html', 'ti-chart-bar'],
    ],
  };

  const esc = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const institutionalApproverTypes = new Set([
    'admin_assistant',
    'administrative_assistant',
    'dean',
    'deputy_vice_chancellor',
    'dvc',
    'faculty_council',
    'faculty_scientific_council',
    'head_of_department',
    'hod',
    'registrar',
    'supervisor',
  ]);
  const normalizeRole = (value) => String(value || '').trim().toLowerCase().replace(/[\s/-]+/g, '_');
  const titleCase = (value) => String(value || '')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

  const approverTypeOf = (user) => {
    const type = normalizeRole(user?.approver_type || AuthManager.getApproverType());
    if (type) return type;
    const role = normalizeRole(user?.role || user?.role_type || AuthManager.getUserRole());
    return institutionalApproverTypes.has(role) ? role : '';
  };
  const roleOf = (user) => {
    const role = normalizeRole(user?.role || user?.role_type || AuthManager.getUserRole());
    if (institutionalApproverTypes.has(role)) return 'approver';
    return role || 'submitter';
  };
  const fullName = (user) => user?.full_name || [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || user?.email || 'FlowDesk user';
  const initials = (user) => fullName(user).split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'F';
  const results = (payload) => payload?.results || payload || [];
  const fmtDate = (value) => value ? new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '-';
  const fmtBytes = (bytes) => {
    const size = Number(bytes || 0);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  function installStyles() {
    if (document.getElementById('flowdesk-shell-style')) return;
    const style = document.createElement('style');
    style.id = 'flowdesk-shell-style';
    style.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
      :root{--fd-primary:#1e40af;--fd-success:#15803d;--fd-danger:#dc2626;--fd-warning:#f59e0b;--fd-sidebar:#0f172a;--fd-muted:#64748b;--fd-border:#e5e7eb;--fd-bg:#f8fafc}
      body{font-family:'DM Sans',Arial,sans-serif;background:#fff;color:#111827}
      .with-sidebar{min-height:100vh;padding-left:200px;background:#fff}
      .sidebar{position:fixed;inset:0 auto 0 0;width:200px;background:#0f172a;color:#fff;display:flex;flex-direction:column;z-index:20}
      .sb-brand{display:flex;align-items:center;gap:8px;height:44px;padding:0 12px;border-bottom:1px solid rgba(255,255,255,.08)}
      .sb-logo{display:grid;place-items:center;width:28px;height:28px;border-radius:7px;background:#1e40af;color:#fff;font-weight:600}
      .sb-name{font-size:13px;font-weight:500}.sb-nav{padding:10px 8px;display:grid;gap:3px}.sb-section{padding:8px 10px 4px;color:rgba(255,255,255,.42);font-size:10px;text-transform:uppercase}
      .nav-item{display:flex;align-items:center;gap:8px;min-height:32px;padding:0 9px;border-radius:6px;color:rgba(255,255,255,.72);font-size:11px}
      .nav-item.active,.nav-item:hover{background:#1e40af;color:#fff}.nav-item .badge-dot{margin-left:auto}
      .sb-foot{margin-top:auto;padding:10px 8px;border-top:1px solid rgba(255,255,255,.08)}.user-row{display:flex;align-items:center;gap:8px}
      .u-ava{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#1e40af;color:#fff;font-size:11px;font-weight:600}.u-name{font-size:11px;font-weight:500}.u-role{font-size:10px;color:rgba(255,255,255,.45);text-transform:capitalize}
      .topbar{position:sticky;top:0;z-index:10;height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;border-bottom:1px solid #e5e7eb;background:#fff}
      .tb-title{font-size:14px;font-weight:500}.tb-right{display:flex;align-items:center;gap:8px}.notif-btn{position:relative;display:grid;place-items:center;width:30px;height:30px;border:1px solid #e5e7eb;border-radius:6px;background:#fff;color:#334155;cursor:pointer}
      .badge-dot{display:inline-grid;place-items:center;min-width:15px;height:15px;padding:0 4px;border-radius:999px;background:#dc2626;color:#fff;font-size:9px;line-height:1}
      .page-area{padding:16px}.main-col{display:grid;gap:16px}.stats-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.stat{padding:14px;border:1px solid #e5e7eb;border-radius:6px;background:#fff}.stat-label{font-size:10px;color:#64748b}.stat-val{margin-top:4px;font-size:20px;font-weight:600}.stat-sub{margin-top:2px;font-size:10px;color:#64748b}
      .card{box-shadow:none}.card-hd{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.card-title{font-size:13px;font-weight:500}
      .tbl{width:100%;border-collapse:collapse;font-size:11px}.tbl th{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;color:#64748b;font-weight:500}.tbl td{padding:9px 8px;border-bottom:1px solid #f1f5f9;vertical-align:middle}.tbl tr[data-href]{cursor:pointer}.tbl tr[data-href]:hover{background:#f8fafc}
      .pill{display:inline-flex;align-items:center;gap:4px;min-height:18px;padding:2px 7px;border-radius:999px;font-size:10px;font-weight:500;text-transform:capitalize}.pill-blue{background:#dbeafe;color:#1e40af}.pill-green{background:#dcfce7;color:#15803d}.pill-amber{background:#fef3c7;color:#92400e}.pill-red{background:#fee2e2;color:#dc2626}.pill-gray{background:#f1f5f9;color:#475569}
      .sla-bar{display:grid;gap:3px;min-width:110px}.sla-track{height:6px;border-radius:999px;background:#e5e7eb;overflow:hidden}.sla-fill{height:100%;width:0;background:#15803d}.sla-fill.warning{background:#f59e0b}.sla-fill.danger{background:#dc2626}.sla-fill.info{background:#1e40af}
      .upload-zone{display:grid;place-items:center;gap:6px;min-height:104px;padding:14px;border:1px dashed #cbd5e1;border-radius:6px;background:#f8fafc;color:#475569;text-align:center;cursor:pointer}
      .modal-backdrop{position:fixed;inset:0;z-index:50;display:grid;place-items:center;padding:16px;background:rgba(15,23,42,.46)}.modal{width:min(480px,100%);max-height:90vh;overflow:auto;border-radius:6px;background:#fff}.modal-header,.modal-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 14px;border-bottom:1px solid #e5e7eb}.modal-footer{border-top:1px solid #e5e7eb;border-bottom:0}.modal-body{padding:14px}
      .approval-card{border:1px solid #e5e7eb;border-radius:6px;background:#fff;padding:12px;display:grid;gap:10px}.approval-card-hd{display:flex;justify-content:space-between;gap:10px}.approval-actions{display:flex;flex-wrap:wrap;gap:8px}
      .form-select{width:100%;min-height:2.5rem;padding:.5rem .75rem;border:1px solid #d1d5db;border-radius:.5rem;background:#fff;color:#111827}.form-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .btn-success{background:#15803d;color:#fff}.btn-success:hover{background:#166534;color:#fff}
      .notif-panel{position:absolute;right:16px;top:42px;width:300px;max-height:360px;overflow:auto;border:1px solid #e5e7eb;border-radius:6px;background:#fff;z-index:40}.notif-item{display:flex;gap:8px;padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:11px;cursor:pointer}.notif-item:hover{background:#f8fafc}
      .banner{padding:9px 10px;border-radius:6px;font-size:11px}.banner.success{background:#f0fdf4;color:#15803d}.banner.error{background:#fee2e2;color:#dc2626}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
      .mob-menu-btn{display:none;align-items:center;justify-content:center;width:32px;height:32px;border:1px solid #e5e7eb;border-radius:6px;background:#fff;color:#334155;cursor:pointer;font-size:16px}
      .sb-overlay{display:none;position:fixed;inset:0;z-index:19;background:rgba(0,0,0,.45)}
      @media(max-width:900px){
        .mob-menu-btn{display:flex}
        .with-sidebar{padding-left:0}
        .sidebar{transform:translateX(-100%);transition:transform .25s ease}
        .sidebar.open{transform:translateX(0)}
        .sb-overlay.open{display:block}
        .sb-close{display:flex !important}
        .stats-row,.form-row{grid-template-columns:1fr}
        .page-area{padding:12px}
        .tbl{font-size:10px}
        .tbl th,.tbl td{padding:6px 4px}
      }
    `;
    document.head.appendChild(style);
  }

  async function consumeUrlTokens() {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const query = new URLSearchParams(window.location.search);
    const access = hash.get('access') || query.get('access');
    const refresh = hash.get('refresh') || query.get('refresh');
    if (access) {
      AuthManager.setTokens({ access, refresh });
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }
    const magicToken = query.get('token');
    if (magicToken) {
      const data = await api.get(`/api/auth/magic-link/verify/?token=${encodeURIComponent(magicToken)}`);
      AuthManager.setTokens(data);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  async function requireUser() {
    await consumeUrlTokens();
    if (!AuthManager.isLoggedIn()) {
      window.location.href = loginUrl;
      throw new Error('Not authenticated');
    }
    const user = await AuthAPI.me();
    AuthManager.setTokens({ access: AuthManager.getAccessToken(), refresh: AuthManager.getRefreshToken(), user });
    return user;
  }

  function roleAllowed(user, allowedRoles) {
    if (!allowedRoles || !allowedRoles.length) return true;
    const allowed = allowedRoles.map(normalizeRole);
    return allowed.includes(roleOf(user)) || allowed.includes(approverTypeOf(user));
  }

  function notificationIcon(type, payload = {}) {
    if (type === 'approval.decision' && payload.decision === 'rejected') return ['ti-x', 'pill-red'];
    if (type === 'approval.decision') return ['ti-circle-check', 'pill-green'];
    if (type === 'approval.approved') return ['ti-circle-check', 'pill-green'];
    if (type === 'approval.rejected') return ['ti-x', 'pill-red'];
    if (type === 'approval.returned') return ['ti-arrow-back-up', 'pill-amber'];
    if (type === 'approval.step_completed') return ['ti-progress-check', 'pill-blue'];
    if (type === 'sla.warning') return ['ti-alert-triangle', 'pill-amber'];
    return ['ti-bell', 'pill-blue'];
  }

  function readNotifications() {
    try { return JSON.parse(localStorage.getItem('flowdesk.notifications') || '[]'); } catch (error) { return []; }
  }

  function writeNotifications(items) {
    localStorage.setItem('flowdesk.notifications', JSON.stringify(items.slice(0, 10)));
    renderNotificationList();
  }

  function messageFor(type, payload = {}) {
    const workflow = payload.workflow_type || payload.workflow_name || 'workflow';
    const office = payload.office || payload.office_name || payload.role || 'office';
    if (type === 'approval.requested') return `Your ${workflow} request is pending approval at ${office}`;
    if (type === 'approval.decision' && payload.decision === 'rejected') return `${office} rejected your ${workflow} request. Feedback available.`;
    if (type === 'approval.decision') return payload.steps_remaining ? `${office} approved your ${workflow} request - ${payload.steps_remaining} steps remaining` : `Your ${workflow} request has been fully approved`;
    if (type === 'approval.step_completed') return payload.message || `Your ${workflow} request moved to the next approval step`;
    if (type === 'approval.approved') return payload.message || `Your ${workflow} request has been fully approved`;
    if (type === 'approval.rejected') return payload.message || `Your ${workflow} request has been rejected`;
    if (type === 'approval.returned') return payload.message || `Your ${workflow} request was returned for corrections`;
    if (type === 'sla.warning') return `Your ${workflow} request is ${payload.percentage || payload.level || ''}% through its deadline`;
    return payload.message || `${titleCase(type)} update`;
  }

  function addNotification(type, payload = {}) {
    const items = readNotifications();
    items.unshift({ id: crypto.randomUUID(), type, payload, message: messageFor(type, payload), createdAt: Date.now(), read: false });
    writeNotifications(items);
  }

  function renderNotificationList() {
    const panel = document.getElementById('notification-panel');
    const badge = document.getElementById('notification-badge');
    const items = readNotifications();
    const unread = items.filter((item) => !item.read).length;
    if (badge) {
      badge.textContent = unread > 9 ? '9+' : `${unread}`;
      badge.classList.toggle('hidden', unread === 0);
    }
    if (!panel) return;
    panel.innerHTML = `
      ${items.length ? items.map((item) => {
        const [icon, pill] = notificationIcon(item.type, item.payload);
        const minutes = Math.max(Math.floor((Date.now() - item.createdAt) / 60000), 0);
        return `<div class="notif-item" data-notification-id="${esc(item.id)}" data-workflow-id="${esc(item.payload?.workflow_id || '')}">
          <span class="pill ${pill}"><i class="ti ${icon}" aria-hidden="true"></i></span>
          <span><span class="block">${esc(item.message)}</span><span class="block text-gray-500">${minutes < 1 ? 'Just now' : `${minutes} minutes ago`}</span></span>
        </div>`;
      }).join('') : '<div class="notif-item"><span>No notifications yet.</span></div>'}
      <button class="btn btn-sm btn-secondary w-full" type="button" id="mark-notifications-read">Mark all as read</button>
    `;
    panel.querySelectorAll('[data-notification-id]').forEach((row) => {
      row.addEventListener('click', () => {
        const next = readNotifications().map((item) => item.id === row.dataset.notificationId ? { ...item, read: true } : item);
        writeNotifications(next);
        if (row.dataset.workflowId) window.location.href = `/static/pages/workflow-detail.html?id=${row.dataset.workflowId}`;
      });
    });
    panel.querySelector('#mark-notifications-read')?.addEventListener('click', () => {
      writeNotifications(readNotifications().map((item) => ({ ...item, read: true })));
    });
  }

  function wireLiveNotifications() {
    const existing = window.notificationManager || (typeof notificationManager !== 'undefined' ? notificationManager : null);
    if (existing?._flowdeskShellWired) return;
    initNotifications();
    const manager = window.notificationManager || (typeof notificationManager !== 'undefined' ? notificationManager : null);
    if (!manager) return;
    manager._flowdeskShellWired = true;
    ['approval.requested', 'approval.decision', 'approval.step_completed', 'approval.approved', 'approval.rejected', 'approval.returned', 'workflow.status_changed', 'sla.warning'].forEach((type) => {
      manager.on(type, (payload) => {
        addNotification(type, payload || {});
        (liveHandlers[type] || []).forEach((handler) => handler(payload || {}));
      });
    });
  }

  function renderSidebar(activePage, user, pendingCount = 0) {
    const role = roleOf(user);
    const nav = navByRole[role] || navByRole.submitter;
    return `
      <aside class="sidebar">
        <div class="sb-brand" style="justify-content:space-between">
          <div style="display:flex;align-items:center;gap:8px"><span class="sb-logo">F</span><span class="sb-name">FlowDesk</span></div>
          <button class="sb-close" id="sb-close-btn" type="button" aria-label="Close menu" style="display:none;align-items:center;justify-content:center;width:26px;height:26px;border:1px solid rgba(255,255,255,.2);border-radius:5px;background:transparent;color:rgba(255,255,255,.7);cursor:pointer"><i class="ti ti-x" aria-hidden="true"></i></button>
        </div>
        <nav class="sb-nav">
          <div class="sb-section">Workspace</div>
          ${nav.map(([key, label, href, icon]) => `
            <a class="nav-item ${activePage === key ? 'active' : ''}" href="${href}">
              <i class="ti ${icon}" aria-hidden="true"></i><span>${label}</span>
              ${key === 'approvals' && pendingCount ? `<span class="badge-dot">${pendingCount > 9 ? '9+' : pendingCount}</span>` : ''}
            </a>
          `).join('')}
        </nav>
       <div class="sb-foot">
          <a class="user-row" href="/static/pages/profile.html" style="text-decoration:none">
            <span class="u-ava">${esc(initials(user))}</span>
            <span><span class="u-name block">${esc(fullName(user))}</span><span class="u-role block">${esc(user.display_role || role)}</span></span>
          </a>
          <button onclick="AuthManager.logout()" type="button" style="margin-top:8px;width:100%;min-height:28px;border:1px solid rgba(255,255,255,.15);border-radius:5px;background:transparent;color:rgba(255,255,255,.6);font-size:11px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px">
            <i class="ti ti-logout" aria-hidden="true"></i> Sign out
          </button>
        </div>
      </aside>
    `;
  }

  function renderShell(activePage, title, user, options = {}) {
    installStyles();
    const role = roleOf(user);
    document.body.className = 'with-sidebar';
    document.body.innerHTML = `
      <div id="sb-overlay" class="sb-overlay"></div>
      ${renderSidebar(activePage, user, options.pendingCount || 0)}
      <header class="topbar">
        <button class="mob-menu-btn" id="mob-menu-btn" type="button" aria-label="Open menu"><i class="ti ti-menu-2" aria-hidden="true"></i></button>
        <div class="tb-title">${esc(title)}</div>
        <div class="tb-right">
          ${role === 'submitter' && !options.hideNewRequest ? '<a class="btn btn-primary btn-sm" href="/static/pages/new-request.html"><i class="ti ti-file-plus" aria-hidden="true"></i> New request</a>' : ''}
          ${options.topbarAction || ''}
          <button class="notif-btn" type="button" id="notification-toggle" aria-label="Notifications"><i class="ti ti-bell" aria-hidden="true"></i><span id="notification-badge" class="badge-dot hidden">0</span></button>
          <div id="notification-panel" class="notif-panel hidden"></div>
        </div>
      </header>
      <main class="page-area"><div id="page-root" class="main-col"></div></main>
      <div id="toast-container" class="fixed bottom-4 right-4 z-50 space-y-2"></div>
    `;
    document.getElementById('notification-toggle')?.addEventListener('click', () => {
      const panel = document.getElementById('notification-panel');
      panel.classList.toggle('hidden');
      renderNotificationList();
    });

    const sidebar = document.querySelector('.sidebar');
    const sbOverlay = document.getElementById('sb-overlay');
    const openSidebar = () => { sidebar?.classList.add('open'); sbOverlay?.classList.add('open'); };
    const closeSidebar = () => { sidebar?.classList.remove('open'); sbOverlay?.classList.remove('open'); };
    document.getElementById('mob-menu-btn')?.addEventListener('click', openSidebar);
    document.getElementById('sb-close-btn')?.addEventListener('click', closeSidebar);
    sbOverlay?.addEventListener('click', closeSidebar);

    renderNotificationList();
    wireLiveNotifications();
    return document.getElementById('page-root');
  }

  async function initPage({ activePage, title, allowedRoles, options = {} }) {
    await consumeUrlTokens();
    if (!AuthManager.isLoggedIn()) {
      window.location.href = loginUrl;
      throw new Error('Not authenticated');
    }
    const tokenUser = { role: AuthManager.getUserRole(), approver_type: AuthManager.getApproverType() };
    if (allowedRoles?.length && tokenUser.role && !roleAllowed(tokenUser, allowedRoles)) {
      window.location.href = dashboardUrl;
      throw new Error('Access denied');
    }
    const user = await requireUser();
    if (!roleAllowed(user, allowedRoles)) {
      window.location.href = dashboardUrl;
      throw new Error('Access denied');
    }
    return { user, root: renderShell(activePage, title, user, options) };
  }

  function onLive(type, handler) {
    liveHandlers[type] = liveHandlers[type] || [];
    liveHandlers[type].push(handler);
  }

  return {
    esc,
    titleCase,
    normalizeRole,
    roleOf,
    approverTypeOf,
    fullName,
    initials,
    results,
    fmtDate,
    fmtBytes,
    initPage,
    renderShell,
    onLive,
    dashboardUrl,
    loginUrl,
  };
})();
