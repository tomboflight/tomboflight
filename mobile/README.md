# Tomb of Light Mobile

Customer-facing mobile app scaffold for Tomb of Light.

## Stack

- Expo
- React Native
- TypeScript
- Expo Router

## Commands

```bash
nvm use
npm install
npx expo install
npm run typecheck
npm run start
npm run build:web
```

## Environment

```bash
# Same-Mac local backend testing
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
EXPO_PUBLIC_ENV=development

# Phone on same LAN (replace with your Mac IP)
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.50:8000
EXPO_PUBLIC_ENV=development
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

## Notes

- Use Node LTS (20.x or 22.x). Newer Node 25 can cause Expo CLI runtime errors.
- This scaffold is intentionally minimal and production-oriented.
- TODO markers show where FastAPI backend integration should be added.
- Keep admin tools out of the mobile MVP.
