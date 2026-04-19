export type SessionSnapshot = {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: string;
};

/**
 * Temporary in-memory session store for scaffold behavior.
 * TODO: Replace with encrypted device storage (for example, expo-secure-store).
 */
let inMemorySession: SessionSnapshot | null = null;

export const storageService = {
  async getSession(): Promise<SessionSnapshot | null> {
    return inMemorySession ? { ...inMemorySession } : null;
  },
  async setSession(session: SessionSnapshot): Promise<void> {
    inMemorySession = { ...session };
    return;
  },
  async clearSession(): Promise<void> {
    inMemorySession = null;
    return;
  }
};
