/// <reference types="jest" />

type JsonRecord = Record<string, unknown>;

type MockResponse = {
  ok: boolean;
  status: number;
  headers: { get: (key: string) => string | null };
  json: () => Promise<unknown>;
  text: () => Promise<string>;
};

function createJsonResponse(status: number, payload: JsonRecord): MockResponse {
  const contentType = 'application/json';

  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key: string) => {
        const normalized = key.toLowerCase();
        if (normalized === 'content-type') {
          return contentType;
        }
        return null;
      }
    },
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  };
}

function createTextResponse(status: number, body: string): MockResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key: string) => {
        const normalized = key.toLowerCase();
        if (normalized === 'content-type') {
          return 'text/plain';
        }
        return null;
      }
    },
    json: async () => {
      throw new Error('Not JSON');
    },
    text: async () => body
  };
}

describe('auth service integration', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    global.fetch = jest.fn() as unknown as typeof fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it('returns MFA challenge without authenticating local session', async () => {
    const authState = require('./auth-state') as typeof import('./auth-state');
    const authService = require('./auth.service') as typeof import('./auth.service');

    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValueOnce(
      createJsonResponse(200, {
        access_token: '',
        token_type: 'bearer',
        mfa_required: true,
        mfa_challenge_token: 'challenge-token-123'
      })
    );

    await authState.saveAccessToken('existing-token');

    const response = await authService.signIn({
      email: 'customer@example.com',
      password: 'valid-password'
    });

    expect(response.mfa_required).toBe(true);
    expect(response.mfa_challenge_token).toBe('challenge-token-123');
    expect(authState.getAuthState().isAuthenticated).toBe(false);
    expect(authState.getAccessToken()).toBeNull();
  });

  it('persists token after successful MFA login verification', async () => {
    const authState = require('./auth-state') as typeof import('./auth-state');
    const authService = require('./auth.service') as typeof import('./auth.service');

    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValueOnce(
      createJsonResponse(200, {
        access_token: 'mfa-final-token',
        token_type: 'bearer'
      })
    );

    await authService.verifyMfaLogin({
      mfaChallengeToken: 'challenge-token-456',
      code: '123456'
    });

    expect(authState.getAuthState().isAuthenticated).toBe(true);
    expect(authState.getAccessToken()).toBe('mfa-final-token');
  });

  it('rejects MFA verify when both code and recovery code are provided', async () => {
    const authService = require('./auth.service') as typeof import('./auth.service');

    await expect(
      authService.verifyMfaLogin({
        mfaChallengeToken: 'challenge-token-789',
        code: '123456',
        recoveryCode: 'RECOVERY123'
      })
    ).rejects.toThrow('Use either an authenticator code or a recovery code, not both.');

    const fetchMock = global.fetch as unknown as jest.Mock;
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('clears local auth state even when logout request fails', async () => {
    const authState = require('./auth-state') as typeof import('./auth-state');
    const authService = require('./auth.service') as typeof import('./auth.service');

    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValueOnce(createTextResponse(500, 'server error'));

    await authState.saveAccessToken('existing-token');

    await expect(authService.signOut()).rejects.toThrow('server error');
    expect(authState.getAuthState().isAuthenticated).toBe(false);
    expect(authState.getAccessToken()).toBeNull();
  });
});
