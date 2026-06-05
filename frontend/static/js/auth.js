const STORAGE_KEY = 'flowdesk.auth.tokens';

const AuthManager = (() => {
  const loadSavedAuth = () => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY);
      return {};
    }
  };

  const decodeTokenPayload = (token) => {
    if (!token) return {};
    try {
      const payload = token.split('.')[1];
      const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
      const padded = normalized.padEnd(normalized.length + ((4 - normalized.length % 4) % 4), '=');
      return JSON.parse(atob(padded));
    } catch (error) {
      return {};
    }
  };

  const isTokenExpired = (token, skewSeconds = 30) => {
    const { exp } = decodeTokenPayload(token);
    if (!exp) return false;
    return Date.now() >= (Number(exp) - skewSeconds) * 1000;
  };

  const saved = loadSavedAuth();
  let accessToken = saved.access || null;
  let refreshToken = saved.refresh || null;
  let currentUser = saved.user || null;

  const persist = () => {
    if (accessToken || refreshToken || currentUser) {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ access: accessToken, refresh: refreshToken, user: currentUser })
      );
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  return {
    setTokens(tokens) {
      accessToken = tokens.access || null;
      refreshToken = tokens.refresh || null;
      currentUser = tokens.user || currentUser;
      persist();
    },

    setAccessToken(token) {
      accessToken = token;
      persist();
    },

    getAccessToken() {
      if (accessToken && isTokenExpired(accessToken)) {
        accessToken = null;
        persist();
      }
      return accessToken;
    },

    getRefreshToken() {
      if (refreshToken && isTokenExpired(refreshToken)) {
        accessToken = null;
        refreshToken = null;
        currentUser = null;
        persist();
      }
      return refreshToken;
    },

    getUser() {
      return currentUser;
    },

    getUserRole() {
      return currentUser?.role || currentUser?.role_type || decodeTokenPayload(accessToken).role || '';
    },

    isAdmin() {
      return this.getUserRole() === 'admin';
    },

    getDefaultRedirect() {
      return this.isAdmin() ? '/admin/config/' : '/';
    },

    isLoggedIn() {
      return Boolean(this.getAccessToken() || this.getRefreshToken());
    },

    clear() {
      accessToken = null;
      refreshToken = null;
      currentUser = null;
      persist();
    },

    consumeRedirectTokens() {
      const params = new URLSearchParams(window.location.hash.slice(1));
      const access = params.get('access');
      const refresh = params.get('refresh');
      if (!access || !refresh) return false;

      this.setTokens({ access, refresh });
      window.history.replaceState({}, document.title, window.location.pathname);
      return true;
    },

    enforcePageAccess() {
      this.consumeRedirectTokens();
      const isLoginPage = window.location.pathname === '/login/';
      if (!this.isLoggedIn() && !isLoginPage) window.location.href = '/login/';
      if (this.isLoggedIn() && isLoginPage) window.location.href = this.getDefaultRedirect();
    },

    async login(username, password) {
      const data = await AuthAPI.login({ username, password });
      accessToken = data.access;
      refreshToken = data.refresh || null;
      currentUser = data.user || null;
      persist();
      return data;
    },

    async signup(payload) {
      const data = await AuthAPI.signup(payload);
      this.setTokens(data);
      return data;
    },

    async requestMagicLink(email) {
      return AuthAPI.requestMagicLink({ email });
    },

    async logout() {
      try {
        await AuthAPI.logout();
      } catch (error) {}

      accessToken = null;
      refreshToken = null;
      currentUser = null;
      persist();
      window.location.href = '/login/';
    },
  };
})();
