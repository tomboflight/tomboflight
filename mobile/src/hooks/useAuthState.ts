import { useEffect, useState } from 'react';

import { AuthState, bootstrapAuthState, getAuthState, subscribeAuthState } from '../services/auth';

/**
 * React hook wrapper for global auth state.
 */
export function useAuthState(): AuthState {
  const [state, setState] = useState<AuthState>(() => getAuthState());

  useEffect(() => {
    const unsubscribe = subscribeAuthState(setState);
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (state.status === 'idle') {
      void bootstrapAuthState();
    }
  }, [state.status]);

  return state;
}
