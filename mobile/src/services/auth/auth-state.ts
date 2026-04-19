import { storageService } from '../storage';

export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'unauthenticated';

export type AuthState = {
  status: AuthStatus;
  accessToken: string | null;
  isAuthenticated: boolean;
};

type Listener = (state: AuthState) => void;

const listeners = new Set<Listener>();
let bootstrapPromise: Promise<AuthState> | null = null;
let authState: AuthState = {
  status: 'idle',
  accessToken: null,
  isAuthenticated: false
};

function publish(nextState: AuthState): void {
  authState = nextState;
  listeners.forEach((listener) => listener(authState));
}

export function getAuthState(): AuthState {
  return authState;
}

export function subscribeAuthState(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getAccessToken(): string | null {
  return authState.accessToken;
}

export async function bootstrapAuthState(): Promise<AuthState> {
  if (bootstrapPromise) {
    return bootstrapPromise;
  }

  bootstrapPromise = (async () => {
    publish({
      status: 'loading',
      accessToken: authState.accessToken,
      isAuthenticated: Boolean(authState.accessToken)
    });

    const session = await storageService.getSession();
    const token = session?.accessToken?.trim() || null;
    const nextState: AuthState = token
      ? {
          status: 'authenticated',
          accessToken: token,
          isAuthenticated: true
        }
      : {
          status: 'unauthenticated',
          accessToken: null,
          isAuthenticated: false
        };

    publish(nextState);
    return nextState;
  })();

  try {
    return await bootstrapPromise;
  } finally {
    bootstrapPromise = null;
  }
}

export async function saveAccessToken(accessToken: string): Promise<void> {
  const token = accessToken.trim();
  if (!token) {
    throw new Error('Cannot save an empty access token.');
  }

  await storageService.setSession({ accessToken: token });
  publish({
    status: 'authenticated',
    accessToken: token,
    isAuthenticated: true
  });
}

export async function clearAccessToken(): Promise<void> {
  await storageService.clearSession();
  publish({
    status: 'unauthenticated',
    accessToken: null,
    isAuthenticated: false
  });
}
