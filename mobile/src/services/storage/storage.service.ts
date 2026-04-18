export type SessionSnapshot = {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: string;
};

/**
 * TODO: replace with secure token storage implementation.
 */
export const storageService = {
  async getSession(): Promise<SessionSnapshot | null> {
    return null;
  },
  async setSession(_session: SessionSnapshot): Promise<void> {
    return;
  },
  async clearSession(): Promise<void> {
    return;
  }
};
