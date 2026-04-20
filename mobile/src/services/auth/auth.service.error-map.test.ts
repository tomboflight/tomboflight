/// <reference types="jest" />

import { ApiConnectivityError, ApiError } from '../api';
import { mapAuthError } from './auth.service';

describe('mapAuthError', () => {
  it('maps network connectivity failures', () => {
    const error = new ApiConnectivityError({
      issue: 'network',
      message: 'network unreachable',
      url: 'https://tomboflight-api.onrender.com/auth/login',
      method: 'POST',
      likelyCors: false
    });

    expect(mapAuthError(error, 'signIn')).toBe(
      'Unable to reach Tomb of Light services. Check your connection and try again.'
    );
  });

  it('maps likely CORS failures on web', () => {
    const error = new ApiConnectivityError({
      issue: 'network',
      message: 'cors blocked',
      url: 'https://tomboflight-api.onrender.com/auth/login',
      method: 'POST',
      likelyCors: true
    });

    expect(mapAuthError(error, 'signIn')).toBe(
      'This web app origin is not currently allowed by the API CORS policy.'
    );
  });

  it('maps timeout failures', () => {
    const error = new ApiConnectivityError({
      issue: 'timeout',
      message: 'timeout',
      url: 'https://tomboflight-api.onrender.com/auth/login',
      method: 'POST'
    });

    expect(mapAuthError(error, 'signIn')).toBe(
      'Tomb of Light services took too long to respond. Please try again.'
    );
  });

  it('maps 401 unauthorized on sign-in', () => {
    const error = new ApiError(401, 'API request failed (401).');
    expect(mapAuthError(error, 'signIn')).toBe('Email or password is incorrect.');
  });

  it('maps 422 validation fallback when detail is unavailable', () => {
    const error = new ApiError(422, 'API request failed (422).');
    expect(mapAuthError(error, 'signIn')).toBe(
      'Sign-in details are invalid. Confirm your email and password format.'
    );
  });

  it('maps 500 server error', () => {
    const error = new ApiError(500, 'API request failed (500).');
    expect(mapAuthError(error, 'signIn')).toBe(
      'Tomb of Light services are temporarily unavailable. Please try again shortly.'
    );
  });
});
