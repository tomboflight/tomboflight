/// <reference types="jest" />

jest.mock('../storage', () => ({
  storageService: {
    getSession: jest.fn(),
    setSession: jest.fn(),
    clearSession: jest.fn()
  }
}));

function loadModules() {
  const storageModule = require('../storage') as {
    storageService: {
      getSession: jest.Mock;
      setSession: jest.Mock;
      clearSession: jest.Mock;
    };
  };
  const authState = require('./auth-state') as typeof import('./auth-state');
  return { storageService: storageModule.storageService, authState };
}

describe('auth-state', () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it('bootstraps authenticated state when session token exists', async () => {
    const { storageService, authState } = loadModules();
    storageService.getSession.mockResolvedValueOnce({
      accessToken: 'stored-token'
    });

    const result = await authState.bootstrapAuthState();

    expect(result.isAuthenticated).toBe(true);
    expect(result.accessToken).toBe('stored-token');
    expect(authState.getAccessToken()).toBe('stored-token');
  });

  it('bootstraps unauthenticated state when no session is stored', async () => {
    const { storageService, authState } = loadModules();
    storageService.getSession.mockResolvedValueOnce(null);

    const result = await authState.bootstrapAuthState();

    expect(result.isAuthenticated).toBe(false);
    expect(result.accessToken).toBeNull();
  });

  it('saves and clears token through storage service', async () => {
    const { storageService, authState } = loadModules();
    storageService.setSession.mockResolvedValueOnce(undefined);
    storageService.clearSession.mockResolvedValueOnce(undefined);

    await authState.saveAccessToken('new-token');
    expect(storageService.setSession).toHaveBeenCalledWith({
      accessToken: 'new-token'
    });
    expect(authState.getAuthState().isAuthenticated).toBe(true);

    await authState.clearAccessToken();
    expect(storageService.clearSession).toHaveBeenCalled();
    expect(authState.getAuthState().isAuthenticated).toBe(false);
  });
});
