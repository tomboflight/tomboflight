# Tomb of Light Mobile

Customer-facing iOS and Android app for Tomb of Light.

## Stack

- Expo
- React Native
- TypeScript
- Expo Router

## Commands

```bash
nvm use
npm install
npm run typecheck
npm test
npx expo-doctor
npm run start
npm run build:web
```

## Environment

```bash
# Same-Mac local backend testing
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
EXPO_PUBLIC_ENV=development
EXPO_PUBLIC_SUPPORT_EMAIL=support@tomboflight.com

# Phone on same LAN (replace with your Mac IP)
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.50:8000
EXPO_PUBLIC_ENV=development
EXPO_PUBLIC_SUPPORT_EMAIL=support@tomboflight.com
```

## EAS Build Profiles

```bash
# Development build (dev client)
npx eas-cli build --profile development --platform ios
npx eas-cli build --profile development --platform android

# Internal preview build
npx eas-cli build --profile preview --platform ios
npx eas-cli build --profile preview --platform android

# Production build
npx eas-cli build --profile production --platform ios
npx eas-cli build --profile production --platform android
```

## Current mobile scope

- Customer authentication, MFA challenge/enrollment, password reset request/confirmation, and secure session storage.
- Customer-only project, family, tree, certificates, support, billing-summary, settings, privacy, and data-request flows.
- Native portrait, verification-evidence, and permitted Vault upload intake using the existing FastAPI authorization and idempotency contracts.
- Bearer-protected upload preview/download sharing; private storage URLs are never exposed to the app UI.
- Admin tools remain on the web application.

## Notes

- Use Node LTS (20.x or 22.x). Newer Node 25 can cause Expo CLI runtime errors.
- The hosted API fallback is `https://tomboflight-api.onrender.com`; use a LAN URL only for local backend testing on a physical device.
- Run `npx eas-cli init` once for the connected Expo account before the first EAS build. It adds the project identity to the local app configuration.
- Keep admin tools out of the mobile app.
