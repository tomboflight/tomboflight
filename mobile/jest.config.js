module.exports = {
  preset: 'jest-expo',
  testMatch: ['**/?(*.)+(test|spec).[tj]s?(x)'],
  setupFiles: ['<rootDir>/jest.setup.ts'],
  modulePathIgnorePatterns: ['<rootDir>/.expo/'],
  clearMocks: true
};
