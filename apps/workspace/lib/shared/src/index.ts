/**
 * @evolvxsi-ai/shared — platform-agnostic code shared between EvolvXSI web and mobile.
 *
 * Design tokens are NOT re-exported here: they are generated build artifacts,
 * consumed via the dedicated subpaths "@evolvxsi-ai/shared/tokens.css" (web/Opal CSS
 * variables), "@evolvxsi-ai/shared/nativewind-theme" (mobile Tailwind theme fragment),
 * and "@evolvxsi-ai/shared/native" (mobile light/dark vars() maps).
 */
export * from "./contracts";
export * from "./types";
export * from "./utils";
