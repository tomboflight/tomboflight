import { API_ENDPOINTS } from '../../config';
import { apiRequest } from '../api';
import { clearAccessToken, getAccessToken, saveAccessToken } from './auth-state';

export type SignInInput = {
  email: string;
  password: string;
};

export type SignUpInput = {
  fullName: string;
  email: string;
  password: string;
  termsAccepted: boolean;
  privacyAccepted: boolean;
  eligibilityAttested: boolean;
  policyVersion?: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  csrf_token?: string;
  mfa_required?: boolean;
  mfa_enrollment_required?: boolean;
  mfa_challenge_token?: string | null;
  backup_codes?: string[];
};

export type UserSignupResponse = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
};

export type PasswordResetResponse = {
  success: boolean;
  message: string;
  expires_at?: string | null;
  reset_token?: string | null;
  reset_url?: string | null;
  delivery_mode?: string | null;
};

/**
 * Uses FastAPI /auth/login.
 */
export async function signIn(input: SignInInput): Promise<AuthTokenResponse> {
  const response = await apiRequest<AuthTokenResponse>(API_ENDPOINTS.auth.signIn, {
    method: 'POST',
    body: {
      email: input.email.trim().toLowerCase(),
      password: input.password
    }
  });

  if (response.access_token && !response.mfa_required) {
    await saveAccessToken(response.access_token);
  }

  return response;
}

/**
 * Uses FastAPI /auth/signup.
 * TODO: Build sign-up UI fields for policy acceptance and policy version display.
 */
export async function signUp(input: SignUpInput): Promise<UserSignupResponse> {
  return apiRequest<UserSignupResponse>(API_ENDPOINTS.auth.signUp, {
    method: 'POST',
    body: {
      full_name: input.fullName.trim(),
      email: input.email.trim().toLowerCase(),
      password: input.password,
      terms_accepted: input.termsAccepted,
      privacy_accepted: input.privacyAccepted,
      eligibility_attested: input.eligibilityAttested,
      policy_version: input.policyVersion
    }
  });
}

/**
 * Uses FastAPI /auth/password-reset/request.
 * TODO: Implement token-confirm reset flow via /auth/password-reset/confirm.
 */
export async function requestPasswordReset(email: string): Promise<PasswordResetResponse> {
  return apiRequest<PasswordResetResponse>(API_ENDPOINTS.auth.passwordResetRequest, {
    method: 'POST',
    body: {
      email: email.trim().toLowerCase()
    }
  });
}

/**
 * Uses FastAPI /auth/logout and always clears local token state.
 */
export async function signOut(): Promise<void> {
  const token = getAccessToken() || undefined;

  try {
    await apiRequest(API_ENDPOINTS.auth.logout, {
      method: 'POST',
      token
    });
  } finally {
    await clearAccessToken();
  }
}
