module.exports = {
  content: [
    './frontend/templates/**/*.html',
    './frontend/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        flowdesk: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#0c2d6b',
        },
        status: {
          draft: '#6b7280',
          submitted: '#f59e0b',
          'in-approval': '#3b82f6',
          approved: '#10b981',
          rejected: '#ef4444',
          archived: '#9ca3af',
        },
        sla: {
          'on-track': '#10b981',
          'warning-50': '#f59e0b',
          'warning-75': '#f97316',
          overdue: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Segoe UI', 'Roboto', 'Helvetica Neue', 'sans-serif'],
        mono: ['Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
};
