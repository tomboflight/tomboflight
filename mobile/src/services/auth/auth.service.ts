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

export type MfaEnrollmentBeginResponse = {
  setup_token: string;
  secret: string;
  otpauth_url: string;
};

export type MfaLoginVerifyInput = {
  mfaChallengeToken: string;
  code?: string;
  recoveryCode?: string;
};

async function persistAccessToken(response: AuthTokenResponse): Promise<void> {
  const token = response.access_token?.trim();
  if (token) {
    await saveAccessToken(token);
  }
}

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

  await persistAccessToken(response);

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
 * Starts MFA enrollment after a login challenge.
 */
export async function beginMfaEnrollment(mfaChallengeToken: string): Promise<MfaEnrollmentBeginResponse> {
  return apiRequest<MfaEnrollmentBeginResponse>(API_ENDPOINTS.auth.mfaEnrollBegin, {
    method: 'POST',
    body: {
      mfa_challenge_token: mfaChallengeToken
    }
  });
}

/**
 * Verifies MFA enrollment code and finalizes authenticated session.
 */
export async function verifyMfaEnrollment(setupToken: string, code: string): Promise<AuthTokenResponse> {
  const response = await apiRequest<AuthTokenResponse>(API_ENDPOINTS.auth.mfaEnrollVerify, {
    method: 'POST',
    body: {
      setup_token: setupToken,
      code
    }
  });

  await persistAccessToken(response);
  return response;
}

/**
 * Verifies MFA login challenge and finalizes authenticated session.
 */
export async function verifyMfaLogin(input: MfaLoginVerifyInput): Promise<AuthTokenResponse> {
  const response = await apiRequest<AuthTokenResponse>(API_ENDPOINTS.auth.mfaLoginVerify, {
    method: 'POST',
    body: {
      mfa_challenge_token: input.mfaChallengeToken,
      code: input.code,
      recovery_code: input.recoveryCode
    }
  });

  await persistAccessToken(response);
  return response;
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
