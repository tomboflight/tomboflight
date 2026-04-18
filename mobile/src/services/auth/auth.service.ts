export type SignInInput = {
  email: string;
  password: string;
};

export type SignUpInput = {
  fullName: string;
  email: string;
  password: string;
};

/**
 * TODO: Wire these service methods to the existing FastAPI auth endpoints.
 * Keep endpoint paths and payloads aligned with backend contracts when finalized.
 */
export async function signIn(_input: SignInInput) {
  throw new Error('TODO: Implement sign-in integration with FastAPI backend.');
}

export async function signUp(_input: SignUpInput) {
  throw new Error('TODO: Implement sign-up integration with FastAPI backend.');
}

export async function requestPasswordReset(_email: string) {
  throw new Error('TODO: Implement password reset integration with FastAPI backend.');
}
