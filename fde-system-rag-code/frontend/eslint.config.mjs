import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Experimental React Compiler rule. It flags standard async data-loading
      // and reset effects (loadHistory/loadThreads/loadData) that are correct
      // here. Keep it as a warning so it doesn't block production builds.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
