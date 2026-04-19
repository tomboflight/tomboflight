/// <reference types="jest" />

function loadModules() {
  const secureStore = require('expo-secure-store') as {
    isAvailableAsync: jest.Mock;
    getItemAsync: jest.Mock;
    setItemAsync: jest.Mock;
    deleteItemAsync: jest.Mock;
  };
  const { storageService } = require('./storage.service') as typeof import('./storage.service');
  return { secureStore, storageService };
}

describe('storage service', () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it('persists and reads session from secure storage', async () => {
    const { secureStore, storageService } = loadModules();
    secureStore.isAvailableAsync.mockResolvedValue(true);
    secureStore.getItemAsync.mockResolvedValueOnce(
      JSON.stringify({
        accessToken: 'persisted-token'
      })
    );

    const session = await storageService.getSession();

    expect(session).toEqual({
      accessToken: 'persisted-token',
      refreshToken: undefined,
      expiresAt: undefined
    });
    expect(secureStore.getItemAsync).toHaveBeenCalledTimes(1);
  });

  it('stores normalized session token', async () => {
    const { secureStore, storageService } = loadModules();
    secureStore.isAvailableAsync.mockResolvedValue(true);

    await storageService.setSession({
      accessToken: '  secure-token  '
    });

    expect(secureStore.setItemAsync).toHaveBeenCalledWith(
      'tol.session.v1',
      JSON.stringify({
        accessToken: 'secure-token',
        refreshToken: undefined,
        expiresAt: undefined
      }),
      expect.objectContaining({ keychainService: 'tomboflight.auth' })
    );
  });

  it('clears storage when requested', async () => {
    const { secureStore, storageService } = loadModules();
    secureStore.isAvailableAsync.mockResolvedValue(true);

    await storageService.clearSession();

    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith(
      'tol.session.v1',
      expect.objectContaining({ keychainService: 'tomboflight.auth' })
    );
  });
});
