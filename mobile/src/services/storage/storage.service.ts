import * as SecureStore from 'expo-secure-store';

export type SessionSnapshot = {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: string;
};

/**
 * Session storage for mobile auth.
 * Uses expo-secure-store when available on the runtime platform.
 */
const SESSION_STORAGE_KEY = 'tol.session.v1';
const secureStoreOptions: SecureStore.SecureStoreOptions = {
  keychainService: 'tomboflight.auth'
};

let inMemorySession: SessionSnapshot | null = null;
let secureStoreAvailable: boolean | null = null;

async function isSecureStoreAvailable(): Promise<boolean> {
  if (secureStoreAvailable !== null) {
    return secureStoreAvailable;
  }

  try {
    secureStoreAvailable = await SecureStore.isAvailableAsync();
    return secureStoreAvailable;
  } catch {
    secureStoreAvailable = false;
    return false;
  }
}

function normalizeSession(session: SessionSnapshot): SessionSnapshot {
  const accessToken = session.accessToken.trim();

  if (!accessToken) {
    throw new Error('Access token is required for session storage.');
  }

  return {
    accessToken,
    refreshToken: session.refreshToken?.trim() || undefined,
    expiresAt: session.expiresAt?.trim() || undefined
  };
}

function parseSession(raw: string): SessionSnapshot | null {
  try {
    const parsed = JSON.parse(raw) as SessionSnapshot;
    return normalizeSession(parsed);
  } catch {
    return null;
  }
}

export const storageService = {
  async getSession(): Promise<SessionSnapshot | null> {
    if (inMemorySession) {
      return { ...inMemorySession };
    }

    if (!(await isSecureStoreAvailable())) {
      return null;
    }

    const raw = await SecureStore.getItemAsync(SESSION_STORAGE_KEY, secureStoreOptions);
    if (!raw) {
      return null;
    }

    const session = parseSession(raw);
    if (!session) {
      await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY, secureStoreOptions);
      return null;
    }

    inMemorySession = session;
    return inMemorySession ? { ...inMemorySession } : null;
  },
  async setSession(session: SessionSnapshot): Promise<void> {
    const normalizedSession = normalizeSession(session);
    const serialized = JSON.stringify(normalizedSession);
    inMemorySession = normalizedSession;

    if (await isSecureStoreAvailable()) {
      await SecureStore.setItemAsync(SESSION_STORAGE_KEY, serialized, secureStoreOptions);
    }

    return;
  },
  async clearSession(): Promise<void> {
    inMemorySession = null;

    if (await isSecureStoreAvailable()) {
      await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY, secureStoreOptions);
    }

    return;
  }
};
