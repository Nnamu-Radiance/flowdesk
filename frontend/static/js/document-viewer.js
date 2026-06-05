class DocumentViewer {
  constructor() {
    this.modal = null;
    this.comments = [];
    this.fileUrl = '';
    this.mimeType = '';
    this.options = {};
  }

  async open(fileUrl, mimeType, options = {}) {
    this.fileUrl = fileUrl;
    this.mimeType = mimeType || this.guessMimeType(fileUrl);
    this.options = options;
    this.comments = [];

    this.modal = document.createElement('div');
    this.modal.className = 'document-viewer-backdrop';
    this.modal.innerHTML = `
      <section class="document-viewer-modal" role="dialog" aria-modal="true">
        <header class="document-viewer-header">
          <strong>${this.escape(options.title || 'Review document')}</strong>
          <button class="btn btn-sm btn-secondary" data-close-viewer type="button">
            <i class="ti ti-x" aria-hidden="true"></i> Close
          </button>
        </header>
        <div class="document-viewer-grid">
          <main class="document-viewer-main">
            <div class="document-viewer-toolbar">
              <span class="document-viewer-name">${this.escape(options.filename || fileUrl.split('/').pop() || 'Document')}</span>
            </div>
            <div class="document-viewer-canvas" data-viewer-body>
              <div class="document-viewer-loading">Loading document...</div>
            </div>
          </main>
          <aside class="document-viewer-comments">
            <h3>Comments</h3>
            <div class="form-group">
              <label class="form-label">Comment</label>
              <textarea class="form-input" data-comment-text rows="5"></textarea>
            </div>
            <button class="btn btn-sm btn-secondary" data-add-comment type="button">
              <i class="ti ti-message-plus" aria-hidden="true"></i> Add Comment
            </button>
            <div data-comment-list class="document-comment-list"></div>
          </aside>
        </div>
        <footer class="document-viewer-actions">
          <div class="document-action-group">
            <label class="form-label" for="document-decision">Decision</label>
            <select id="document-decision" class="form-select" data-decision>
              <option value="approved">Approve</option>
              <option value="rejected">Reject</option>
              <option value="returned">Return for Corrections</option>
            </select>
          </div>
          <label class="document-feedback-toggle hidden" data-feedback-wrap>
            <input type="checkbox" data-feedback>
            Send feedback to student
          </label>
          <div class="document-action-buttons">
            <button class="btn btn-secondary" data-close-viewer type="button">Close</button>
            <button class="btn btn-primary" data-submit-review type="button">
              <i class="ti ti-send" aria-hidden="true"></i> Submit Decision
            </button>
          </div>
          <div class="banner error hidden" data-viewer-error></div>
        </footer>
      </section>
    `;
    document.body.appendChild(this.modal);
    this.bindEvents();
    this.renderComments();
    await this.renderDocument();
  }

  bindEvents() {
    this.modal.querySelectorAll('[data-close-viewer]').forEach((button) => {
      button.addEventListener('click', () => this.close());
    });
    this.modal.addEventListener('click', (event) => {
      if (event.target === this.modal) this.close();
    });
    this.modal.querySelector('[data-add-comment]').addEventListener('click', () => this.addComment());
    this.modal.querySelector('[data-submit-review]').addEventListener('click', () => this.submit());
    this.modal.querySelector('[data-decision]').addEventListener('change', () => this.updateFeedbackVisibility());
  }

  async renderDocument() {
    try {
      if (this.mimeType.includes('pdf')) {
        await this.renderPdf();
      } else if (this.mimeType.includes('word') || this.fileUrl.toLowerCase().endsWith('.docx')) {
        await this.renderDocx();
      } else if (this.mimeType.startsWith('image/') || /\.(png|jpe?g)$/i.test(this.fileUrl)) {
        this.renderImage();
      } else {
        this.renderDownload();
      }
    } catch (error) {
      this.modal.querySelector('[data-viewer-body]').innerHTML = `
        <div class="document-viewer-loading">
          Could not preview this file.
          <a class="btn btn-sm btn-secondary" href="${this.escape(this.fileUrl)}" target="_blank" rel="noopener">Download</a>
        </div>
      `;
    }
  }

  async renderPdf() {
    await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js');
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    const buffer = await this.fetchBuffer();
    const pdf = await window.pdfjsLib.getDocument({ data: buffer }).promise;
    const body = this.modal.querySelector('[data-viewer-body]');
    body.innerHTML = '';

    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1.25 });
      const pageWrap = document.createElement('section');
      pageWrap.className = 'document-pdf-page';
      pageWrap.innerHTML = `<div class="document-page-label">Page ${pageNumber} of ${pdf.numPages}</div>`;
      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      pageWrap.appendChild(canvas);
      body.appendChild(pageWrap);
      await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
    }
  }

  async renderDocx() {
    await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js');
    const buffer = await this.fetchBuffer();
    const result = await window.mammoth.convertToHtml({ arrayBuffer: buffer });
    this.modal.querySelector('[data-viewer-body]').innerHTML = `<div class="document-docx-body">${result.value}</div>`;
  }

  renderImage() {
    this.modal.querySelector('[data-viewer-body]').innerHTML = `
      <img class="document-image" src="${this.escape(this.fileUrl)}" alt="">
    `;
  }

  renderDownload() {
    this.modal.querySelector('[data-viewer-body]').innerHTML = `
      <div class="document-viewer-loading">
        Preview is not available for this file type.
        <a class="btn btn-sm btn-secondary" href="${this.escape(this.fileUrl)}" target="_blank" rel="noopener">Download file</a>
      </div>
    `;
  }

  async fetchBuffer() {
    const headers = {};
    const token = AuthManager.getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(this.fileUrl, { headers });
    if (!response.ok) throw new Error('Could not load document');
    return response.arrayBuffer();
  }

  addComment() {
    const input = this.modal.querySelector('[data-comment-text]');
    const text = input.value.trim();
    if (!text) return;
    this.comments.push({ text, timestamp: new Date().toISOString() });
    input.value = '';
    this.renderComments();
  }

  renderComments() {
    const list = this.modal.querySelector('[data-comment-list]');
    if (!list) return;
    list.innerHTML = this.comments.length ? this.comments.map((comment, index) => `
      <div class="document-comment">
        <button class="btn btn-sm btn-secondary" data-remove-comment="${index}" type="button">
          <i class="ti ti-trash" aria-hidden="true"></i>
        </button>
        <span>
          <span class="block text-gray-500">${new Date(comment.timestamp).toLocaleString()}</span>
          <span class="block">${this.escape(comment.text)}</span>
        </span>
      </div>
    `).join('') : '<div class="text-gray-500 text-sm">No comments added.</div>';
    list.querySelectorAll('[data-remove-comment]').forEach((button) => {
      button.addEventListener('click', () => {
        this.comments.splice(Number(button.dataset.removeComment), 1);
        this.renderComments();
      });
    });
  }

  updateFeedbackVisibility() {
    const action = this.modal.querySelector('[data-decision]').value;
    const wrap = this.modal.querySelector('[data-feedback-wrap]');
    const feedback = this.modal.querySelector('[data-feedback]');
    const needsFeedback = action === 'rejected' || action === 'returned';
    wrap.classList.toggle('hidden', !needsFeedback);
    feedback.checked = needsFeedback;
  }

  async submit() {
    const button = this.modal.querySelector('[data-submit-review]');
    const error = this.modal.querySelector('[data-viewer-error]');
    const action = this.modal.querySelector('[data-decision]').value;
    const comments = this.comments.map((comment) => `[${new Date(comment.timestamp).toLocaleString()}] ${comment.text}`).join('\n\n');
    const sendFeedback = this.modal.querySelector('[data-feedback]').checked;

    error.classList.add('hidden');
    button.disabled = true;
    button.innerHTML = '<i class="ti ti-loader" aria-hidden="true"></i> Submitting...';

    try {
      await this.options.onSubmit?.({ action, comments, sendFeedback });
      this.close();
    } catch (submitError) {
      error.textContent = submitError.message || 'Could not submit decision.';
      error.classList.remove('hidden');
      button.disabled = false;
      button.innerHTML = '<i class="ti ti-send" aria-hidden="true"></i> Submit Decision';
    }
  }

  guessMimeType(fileUrl) {
    const lower = String(fileUrl || '').toLowerCase();
    if (lower.endsWith('.pdf')) return 'application/pdf';
    if (lower.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    return '';
  }

  loadScript(src) {
    if (document.querySelector(`script[src="${src}"]`)) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error('Could not load document renderer'));
      document.head.appendChild(script);
    });
  }

  escape(value) {
    if (window.FlowDeskShell?.esc) return FlowDeskShell.esc(value);
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  close() {
    this.modal?.remove();
    this.modal = null;
  }
}

window.DocumentViewer = DocumentViewer;
