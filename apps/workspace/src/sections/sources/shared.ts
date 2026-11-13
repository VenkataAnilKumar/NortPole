export const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
export const pageClass = "mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-8";
export const h1Class = "font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05";

export function titleCase(s: string): string {
  return s.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
