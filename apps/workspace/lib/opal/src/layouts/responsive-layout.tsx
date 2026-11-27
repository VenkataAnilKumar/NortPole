import type { ComponentPropsWithRef } from "react";
import { clsx } from "clsx";

const displayClasses = {
  flex: "flex",
  grid: "grid",
  inlineFlex: "inline-flex",
  inlineGrid: "inline-grid",
};

type ResponsiveLayoutProps = ComponentPropsWithRef<"div"> & {
  as?: "div" | "span";
  display?: keyof typeof displayClasses;
};

/**
 * A layout whose display or spacing can change by breakpoint or state.
 * Spacing stays in CSS so responsive utilities can override it.
 */
export function ResponsiveLayout({
  as: Element = "div",
  display,
  className,
  ...props
}: ResponsiveLayoutProps) {
  return <Element {...props} className={clsx(display && displayClasses[display], className)} />;
}
