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
 * TODO: Connect these functions to existing FastAPI auth endpoints.
 */
export async function signIn(_input: SignInInput) {
  throw new Error('TODO: Implement sign-in integration.');
}

export async function signUp(_input: SignUpInput) {
  throw new Error('TODO: Implement sign-up integration.');
}

export async function requestPasswordReset(_email: string) {
  throw new Error('TODO: Implement password reset integration.');
}
