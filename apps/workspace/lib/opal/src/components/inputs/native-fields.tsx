import type { ComponentPropsWithRef } from "react";

const fieldClassName =
  "rounded-md border border-border-01 bg-background-neutral-00 px-2 py-1 text-text-05";

/** A browser-managed field for native pickers, validation, and custom form layouts. */
export function NativeInput({
  type,
  className,
  ...props
}: ComponentPropsWithRef<"input">) {
  const usesNativeChrome = type === "checkbox" || type === "radio" || type === "file";
  return (
    <input
      {...props}
      type={type}
      className={className ?? (usesNativeChrome ? undefined : fieldClassName)}
    />
  );
}

/** A text area whose native rows and resize behavior are owned by the caller. */
export function NativeTextArea({ className = fieldClassName, ...props }: ComponentPropsWithRef<"textarea">) {
  return <textarea {...props} className={className} />;
}

/** A browser select for forms using native options, focus, and change events. */
export function NativeSelect({ className = fieldClassName, ...props }: ComponentPropsWithRef<"select">) {
  return <select {...props} className={className} />;
}
