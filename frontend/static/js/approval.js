class ApprovalPage {
  constructor(user, root) {
    this.user = user;
    this.root = root;
    this.items = [];
    this.activeFilter = 'all';
    this.viewer = null;
    this.approverType = FlowDeskShell.approverTypeOf(user);
    this.tabs = this.tabsForUser();
  }

  async init() {
    const tabsMarkup = this.tabs.length > 1
      ? `<div id="approval-tabs" style="display:flex;gap:6px">${this.tabs.map((tab) => `<button class="btn btn-sm btn-secondary" data-tab="${tab.value}" type="button">${tab.label}</button>`).join('')}</div>`
      : '';
    this.root.innerHTML = `
      <section class="card">
        <div class="card-hd">
          <h2 class="card-title">Pending approvals</h2>
          ${tabsMarkup}
        </div>
        <div id="approval-list">Loading approvals...</div>
      </section>
    `;
    document.getElementById('approval-tabs')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-tab]');
      if (!button) return;
      this.activeFilter = button.dataset.tab;
      this.render();
    });
    FlowDeskShell.onLive('approval.requested', () => this.load());
    await this.load();
  }

  tabsForUser() {
    if (FlowDeskShell.roleOf(this.user) === 'admin' || this.approverType === 'registrar') {
      return [
        { label: 'All', value: 'all' },
        { label: 'Academic', value: 'academic' },
        { label: 'Finance', value: 'finance' },
        { label: 'Administrative', value: 'administrative' },
      ];
    }
    return [{ label: 'All', value: 'all' }];
  }

  async load() {
    const data = await ApprovalAPI.pending();
    this.items = FlowDeskShell.results(data);
    this.render();
  }

  filtered() {
    if (this.activeFilter === 'all') return this.items;
    return this.items.filter((item) => {
      const haystack = [
        item.workflow_type,
        item.workflow_type_name,
        item.name,
        item.approval_type,
        ...(Array.isArray(item.tags) ? item.tags : []),
      ].join(' ').toLowerCase();
      return haystack.includes(this.activeFilter);
    });
  }

  render() {
    const container = document.getElementById('approval-list');
    const items = this.filtered();
    if (!items.length) {
      container.innerHTML = '<div style="padding:32px;text-align:center;color:#64748b;font-size:11px">No pending approvals.</div>';
      return;
    }
    container.innerHTML = `<div style="display:grid;gap:10px">${items.map((item) => this.card(item)).join('')}</div>`;
    container.querySelectorAll('[data-action]').forEach((button) => {
      button.addEventListener('click', () => this.openModal(button.dataset.action, Number(button.dataset.workflowId), button));
    });
  }

  card(item) {
    const step = item.current_step_number || 1;
    const total = item.total_steps || item.steps?.length || 1;
    const pct = this.slaPct(item);
    const overdue = new Date(item.deadline || 0) < new Date();
    const student = [item.student_name, item.student_matricule, item.student_faculty].filter(Boolean).join(' · ');
    const docs = Array.isArray(item.documents) ? item.documents : [];
    return `
      <article class="approval-card" data-workflow-id="${item.workflow_id}">
        <div class="approval-card-hd">
          <div>
            <strong style="font-size:12px;font-weight:500">${FlowDeskShell.esc(item.workflow_type_name || item.workflow_type || item.name || `Workflow ${item.workflow_id}`)}</strong>
            <span class="block text-gray-500" style="font-size:10px">${FlowDeskShell.esc(student || 'Student information unavailable')}</span>
            <span class="block mono text-gray-500" style="font-size:10px">WF-${FlowDeskShell.esc(item.workflow_id)}</span>
          </div>
          <span class="pill ${overdue ? 'pill-red' : 'pill-blue'}">${overdue ? 'Overdue' : `Step ${step} of ${total}`}</span>
        </div>
        <div class="sla-bar">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:${overdue ? '#dc2626' : '#64748b'}"><span>SLA</span><span>${overdue ? 'Overdue' : `${pct}% · ${this.timeLeft(item.deadline)}`}</span></div>
          <div class="sla-track"><div class="sla-fill ${overdue || pct >= 100 ? 'danger' : pct >= 50 ? 'warning' : ''}" style="width:${Math.min(pct, 100)}%"></div></div>
        </div>
        ${overdue ? '<div style="background:#fee2e2;color:#dc2626;border-radius:4px;padding:6px 8px;font-size:10px">SLA breached - escalation sent to next role in chain</div>' : ''}
        ${docs.length ? `<div style="display:flex;flex-wrap:wrap;gap:6px">${docs.map((doc, index) => `
          <button class="btn btn-sm btn-secondary" data-action="review-document" data-doc-index="${index}" data-workflow-id="${item.workflow_id}" type="button">
            <i class="ti ti-file-search" aria-hidden="true"></i> Review Document
          </button>
        `).join('')}</div>` : ''}
        <div class="approval-actions">
          <button class="btn btn-success btn-sm" data-action="approve" data-workflow-id="${item.workflow_id}" type="button"><i class="ti ti-check" aria-hidden="true"></i> Approve</button>
          <button class="btn btn-danger btn-sm" data-action="reject" data-workflow-id="${item.workflow_id}" type="button"><i class="ti ti-x" aria-hidden="true"></i> Reject</button>
          <button class="btn btn-sm btn-secondary" data-action="reassign" data-workflow-id="${item.workflow_id}" type="button"><i class="ti ti-transfer" aria-hidden="true"></i> Reassign</button>
          <button class="btn btn-sm btn-secondary" data-action="history" data-workflow-id="${item.workflow_id}" type="button"><i class="ti ti-history" aria-hidden="true"></i> History</button>
        </div>
      </article>
    `;
  }

  itemFor(workflowId) {
    return this.items.find((item) => Number(item.workflow_id) === Number(workflowId)) || {};
  }

  openModal(action, workflowId, trigger = null) {
    if (action === 'review-document') {
      return this.reviewDocument(workflowId, Number(trigger?.dataset.docIndex || 0));
    }
    if (action === 'approve') return this.approveModal(workflowId);
    if (action === 'reject') return this.rejectModal(workflowId);
    if (action === 'reassign') return this.reassignModal(workflowId);
    return this.historyPanel(workflowId);
  }

  reviewDocument(workflowId, docIndex = 0) {
    const item = this.itemFor(workflowId);
    const docs = Array.isArray(item.documents) ? item.documents.filter((doc) => doc.url) : [];
    if (!docs.length) {
      showToast('No readable documents are attached to this workflow.', 'warning');
      return;
    }
    const doc = docs[docIndex] || docs[0];
    this.viewer = new DocumentViewer();
    this.viewer.open(doc.url, doc.mime_type || this.mimeTypeFor(doc.filename || doc.url), {
      title: item.workflow_type_name || 'Review document',
      filename: doc.filename || doc.document_label || 'Document',
      onSubmit: async ({ action, comments, sendFeedback }) => {
        const fd = new FormData();
        fd.append('action', action);
        fd.append('comments', comments);
        fd.append('send_feedback_to_student', sendFeedback ? 'true' : 'false');
        try {
          await api.upload(`/api/approvals/${workflowId}/decision/`, fd);
        } catch (error) {
          if (error.status !== 404) throw error;
          await api.upload(`/api/approvals/${workflowId}/decide/`, fd);
        }
        showToast('Decision submitted.', 'success');
        await this.load();
      },
    }).catch((error) => showToast(error.message, 'error'));
  }

  mimeTypeFor(value) {
    const lower = String(value || '').toLowerCase();
    if (lower.endsWith('.pdf')) return 'application/pdf';
    if (lower.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    return '';
  }

  modal(title, body, footer = '') {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <section class="modal">
        <header class="modal-header"><strong style="font-size:13px">${FlowDeskShell.esc(title)}</strong><button class="btn btn-sm btn-secondary" data-close type="button"><i class="ti ti-x" aria-hidden="true"></i></button></header>
        <div class="modal-body">${body}</div>
        ${footer ? `<footer class="modal-footer">${footer}</footer>` : ''}
      </section>
    `;
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop || event.target.closest('[data-close]')) backdrop.remove();
    });
    document.body.appendChild(backdrop);
    return backdrop;
  }

  approveModal(workflowId) {
    const item = this.itemFor(workflowId);
    const modal = this.modal(`Approve - ${item.workflow_type_name || 'Workflow'}`, `
      <p class="text-gray-600" style="font-size:11px">Add feedback for the student (optional)</p>
      <textarea id="approve-comments" class="form-input" rows="4" placeholder="e.g. Well structured project proposal..."></textarea>
    `, `
      <button class="btn btn-sm btn-secondary" id="approve-empty" type="button">Approve without feedback</button>
      <button class="btn btn-success btn-sm" id="approve-with" type="button">Approve with feedback</button>
    `);
    const submit = async (comments) => {
      await api.post(`/api/approvals/${workflowId}/decide/`, { action: 'approved', comments });
      showToast('Approval recorded.', 'success');
      modal.remove();
      this.load();
    };
    modal.querySelector('#approve-empty').addEventListener('click', () => submit('').catch((error) => showToast(error.message, 'error')));
    modal.querySelector('#approve-with').addEventListener('click', () => submit(modal.querySelector('#approve-comments').value).catch((error) => showToast(error.message, 'error')));
  }

  rejectModal(workflowId) {
    const item = this.itemFor(workflowId);
    const modal = this.modal(`Reject - ${item.workflow_type_name || 'Workflow'}`, `
      <p class="text-gray-600" style="font-size:11px">You must provide feedback to the student explaining the rejection.</p>
      <textarea id="reject-comments" class="form-input" rows="4" placeholder="e.g. Missing authenticated A-level certificate. Please resubmit with..."></textarea>
      <label style="display:flex;align-items:center;gap:6px;margin-top:10px;font-size:11px"><input id="attach-toggle" type="checkbox"> Attach commented document?</label>
      <div id="reject-file-wrap" class="hidden" style="margin-top:10px"><input id="reject-file" class="form-input" type="file"></div>
    `, `<button class="btn btn-danger btn-sm" id="send-rejection" type="button" disabled>Send rejection with feedback</button>`);
    const comments = modal.querySelector('#reject-comments');
    const button = modal.querySelector('#send-rejection');
    comments.addEventListener('input', () => { button.disabled = !comments.value.trim(); });
    modal.querySelector('#attach-toggle').addEventListener('change', (event) => {
      modal.querySelector('#reject-file-wrap').classList.toggle('hidden', !event.target.checked);
    });
    button.addEventListener('click', async () => {
      try {
        const file = modal.querySelector('#reject-file').files[0];
        if (file) {
          const fd = new FormData();
          fd.append('action', 'rejected');
          fd.append('reason', comments.value.trim());
          fd.append('comments', comments.value.trim());
          fd.append('send_feedback_to_student', 'true');
          fd.append('annotated_document', file);
          await api.upload(`/api/approvals/${workflowId}/decide/`, fd);
        } else {
          await api.post(`/api/approvals/${workflowId}/decide/`, { action: 'rejected', reason: comments.value.trim(), send_feedback_to_student: true });
        }
        showToast('Rejection sent with feedback.', 'success');
        modal.remove();
        this.load();
      } catch (error) {
        showToast(error.message, 'error');
      }
    });
  }

  async reassignModal(workflowId) {
    const users = FlowDeskShell.results(await AuthAPI.users().catch(() => []))
      .filter((user) => {
        if (user.id === this.user.id) return false;
        if (FlowDeskShell.roleOf(user) !== 'approver') return false;
        return !this.approverType || FlowDeskShell.approverTypeOf(user) === this.approverType;
      });
    const modal = this.modal('Reassign approval', `
      <div class="form-group"><label class="form-label">Approver</label><select id="reassign-user" class="form-select">${users.map((user) => `<option value="${user.id}">${FlowDeskShell.esc(FlowDeskShell.fullName(user))}</option>`).join('')}</select></div>
      <div class="form-group"><label class="form-label">Note</label><textarea id="reassign-note" class="form-input" rows="3"></textarea></div>
    `, `<button class="btn btn-primary btn-sm" id="reassign-submit" type="button">Reassign</button>`);
    modal.querySelector('#reassign-submit').addEventListener('click', async () => {
      try {
        const newAssigneeId = modal.querySelector('#reassign-user').value;
        if (!newAssigneeId) {
          showToast('No matching approver is available for reassignment.', 'error');
          return;
        }
        await api.post(`/api/approvals/${workflowId}/reassign/`, {
          new_assignee_id: newAssigneeId,
          reason: modal.querySelector('#reassign-note').value,
        });
        showToast('Approval reassigned.', 'success');
        modal.remove();
        this.load();
      } catch (error) {
        showToast(error.message, 'error');
      }
    });
  }

  async historyPanel(workflowId) {
    const records = FlowDeskShell.results(await api.get(`/api/approvals/${workflowId}/history/`).catch(() => []));
    this.modal('Approval history', records.length ? records.map((record) => `
      <div style="padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:11px">
        <strong>${FlowDeskShell.titleCase(record.action || 'Update')}</strong>
        <span class="block text-gray-500">${FlowDeskShell.fmtDate(record.created_at)}</span>
        <span class="block">${FlowDeskShell.esc(record.comments || '')}</span>
      </div>
    `).join('') : '<p class="text-gray-600">No history yet.</p>');
  }

  slaPct(item) {
    if (!item.deadline || !item.created_at) return 0;
    const total = new Date(item.deadline) - new Date(item.created_at);
    const used = Date.now() - new Date(item.created_at);
    return total > 0 ? Math.max(0, Math.min(Math.round((used / total) * 100), 100)) : 100;
  }

  timeLeft(deadline) {
    const ms = new Date(deadline) - new Date();
    if (ms <= 0) return 'Overdue';
    const days = Math.floor(ms / 86400000);
    const hours = Math.floor((ms % 86400000) / 3600000);
    return days ? `${days}d ${hours}h left` : `${hours}h left`;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const { user, root } = await FlowDeskShell.initPage({
      activePage: 'approvals',
      title: 'Pending approvals',
      allowedRoles: ['approver', 'admin', 'registrar', 'hod', 'dean', 'admin_assistant', 'faculty_council', 'dvc', 'supervisor'],
      options: { hideNewRequest: true },
    });
    await new ApprovalPage(user, root).init();
  } catch (error) {
    if (error.message !== 'Not authenticated' && error.message !== 'Access denied') showToast(`Failed to load approvals: ${error.message}`, 'error');
  }
});
