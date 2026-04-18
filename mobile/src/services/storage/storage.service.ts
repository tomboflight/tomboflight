export type SessionSnapshot = {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: string;
};

/**
 * TODO: Replace placeholders with secure token storage (for example, expo-secure-store).
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
