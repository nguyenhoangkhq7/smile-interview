import typescriptEslint from 'typescript-eslint';
import nextPlugin from '@next/eslint-plugin-next';

export default typescriptEslint.config(
  // 1. Global Ignores
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "out/**",
      "build/**",
      "remove_comments.js",
      "postcss.config.js",
    ],
  },
  // 2. TypeScript Recommended Config
  ...typescriptEslint.configs.recommended,
  // 3. Next.js Linting Config
  {
    files: ["src/**/*.{ts,tsx,js,jsx}"],
    plugins: {
      '@next/next': nextPlugin,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs['core-web-vitals'].rules,
      // Custom overrides
      "@typescript-eslint/no-unused-vars": ["warn", { "argsIgnorePattern": "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
    },
  }
);
