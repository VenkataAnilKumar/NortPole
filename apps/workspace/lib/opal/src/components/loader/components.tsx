"use client";

import "@opal/components/loader/styles.css";
import { cn } from "@opal/utils";
import { useOpalStrings } from "@opal/strings";

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

// Marks render in `currentColor`, so color is applied as a text token.
// Default is the neutral `border-02`. Pass `color` to override, or
// `"inherit"` to set no class and let the ambient text color flow through.
type LoaderColor =
  | "inherit"
  | "border-02"
  | "text-02"
  | "text-03"
  | "text-04"
  | "text-05"
  | "status-error-05"
  | "status-success-05"
  | "status-warning-05";

const COLOR_CLASS: Record<LoaderColor, string> = {
  inherit: "",
  "border-02": "text-border-02",
  "text-02": "text-text-02",
  "text-03": "text-text-03",
  "text-04": "text-text-04",
  "text-05": "text-text-05",
  "status-error-05": "text-status-error-05",
  "status-success-05": "text-status-success-05",
  "status-warning-05": "text-status-warning-05",
};

// ---------------------------------------------------------------------------
// NortPoleLoader
// ---------------------------------------------------------------------------

interface NortPoleLoaderProps {
  /** Size of the animated mark, in pixels. @default 64 */
  size?: number;

  /** Mark color token. @default "border-02" */
  color?: LoaderColor;
}

// Geometry is the North Star of `nortpole-logo`, on a 16 grid. Stroke
// is defined here, not reused from them, so weight can be tuned: ~2.5px at
// the default 64px, scaling with `size`.
const STROKE_WIDTH = 0.625;

const OUTLINE_PATH =
  "M8 1L9.4 6.6L14.67 8L9.4 9.4L8 15L6.6 9.4L1.33 8L6.6 6.6Z";

function svgLayerProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    xmlns: "http://www.w3.org/2000/svg",
  };
}

const MARK_PATHS = [
  "M8 1L9.4 6.6L14.67 8L9.4 9.4L8 15L6.6 9.4L1.33 8L6.6 6.6Z",
];

/**
 * NortPole-branded loading mark: turns a half turn while crossfading between the North Star
 * outline and the filled star (2s loop), holding the static outline
 * under `prefers-reduced-motion`. Uses `currentColor`, so `color` themes it.
 * For a full-page loading state with a label, use `PageLoader`.
 */
function NortPoleLoader({
  size = 64,
  color = "border-02",
}: NortPoleLoaderProps) {
  const strings = useOpalStrings();
  return (
    <div
      role="status"
      aria-label={strings.loading}
      className={cn("relative shrink-0", COLOR_CLASS[color])}
      style={{ width: size, height: size }}
    >
      <div className="opal-loader-rotator">
        <svg
          {...svgLayerProps(size)}
          className="opal-loader-layer opal-loader-outline"
        >
          <path
            d={OUTLINE_PATH}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <svg
          {...svgLayerProps(size)}
          className="opal-loader-layer opal-loader-mark"
        >
          {MARK_PATHS.map((d) => (
            <path
              key={d}
              d={d}
              fill="currentColor"
              strokeWidth={STROKE_WIDTH}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
        </svg>
      </div>
    </div>
  );
}

export { NortPoleLoader, type NortPoleLoaderProps, type LoaderColor };
