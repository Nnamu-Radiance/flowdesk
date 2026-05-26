const AuthManager = (() => {
  let accessToken = null;
  let refreshToken = null;

  return {
    setAccessToken(token) {
      accessToken = token;
    },

    getAccessToken() {
      return accessToken;
    },

    getRefreshToken() {
      return refreshToken;
    },

    isLoggedIn() {
      return Boolean(accessToken);
    },

    async login(username, password) {
      const data = await AuthAPI.login({ username, password });
      this.setAccessToken(data.access);
      refreshToken = data.refresh || null;
      return data;
    },

    async logout() {
      try {
        await AuthAPI.logout();
      } catch (error) {
        // Ignore server-side logout failures.
      }

      accessToken = null;
      refreshToken = null;
      window.location.href = '/login/';
    },
  };
})();
