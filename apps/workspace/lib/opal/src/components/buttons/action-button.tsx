import type { ComponentPropsWithRef } from "react";
import { clsx } from "clsx";

/**
 * Action surface for cards, segmented controls, and table rows with rich
 * children. Button supplies the chrome for ordinary labeled actions.
 */
export function ActionButton({ type = "button", className, ...props }: ComponentPropsWithRef<"button">) {
  return (
    <button
      {...props}
      type={type}
      className={clsx("focus-visible:outline-offset-2 disabled:cursor-not-allowed", className)}
    />
  );
}
