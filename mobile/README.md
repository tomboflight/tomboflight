# Tomb of Light Mobile (Expo + React Native + TypeScript)

This folder contains a clean starter for the Tomb of Light customer-facing mobile MVP.

## Scope for this starter

- Expo Router file-based routing
- TypeScript-first structure
- Placeholder screens for customer flows only
- No admin tooling in mobile MVP
- Clear TODO markers for future FastAPI integration

## Structure

- `app/` route entrypoints and navigation layout
- `src/components/` reusable UI shells for MVP placeholder screens
- `src/features/` future domain modules by customer feature
- `src/services/` API/auth/storage integration points
- `src/theme/` design tokens for bright blue/gray/white premium UI direction

## Quick start

```bash
npm install
npm run start
```

Then open iOS/Android simulator or Expo Go from the Metro UI.

## Integration notes

- Set `EXPO_PUBLIC_API_BASE_URL` in `.env`.
- Replace auth/service TODOs with real FastAPI endpoints once backend contract is finalized.
- Keep all mobile-only logic inside this `mobile/` directory.
