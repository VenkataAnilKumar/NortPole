import type { IconProps } from "@opal/types";
import { illustrationStrokeWidth } from "@opal/illustrations/line-weight";
// The NortPole empty state: the North Star over two snowy hills, with faint
// star trails circling it (decision 0007). Neutral tokens only, no accent colour.
const SvgEmpty = ({ size, ...props }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 120 120"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    strokeWidth={illustrationStrokeWidth(size)}
    {...props}
  >
    <path
      d="M8 100C24 80 40 70 56 76C72 82 84 66 112 78V100H8Z"
      fill="var(--background-neutral-03)"
    />
    <path
      d="M8 100C30 88 52 90 70 94C88 98 100 90 112 92V100H8Z"
      fill="var(--background-neutral-00)"
    />
    <path
      d="M8 100C30 88 52 90 70 94C88 98 100 90 112 92"
      stroke="var(--border-03)"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M42 30A20 20 0 0 1 60 14M78 38A20 20 0 0 1 72 52M30 40A32 32 0 0 1 36 22M88 24A32 32 0 0 1 92 44"
      stroke="var(--border-02)"
      strokeLinecap="round"
    />
    <path
      d="M24 56h.01M96 60h.01M20 24h.01M100 14h.01M44 62h.01"
      stroke="var(--border-03)"
      strokeLinecap="round"
    />
    <path
      d="M60 23.5L62.1 31.9L70 34L62.1 36.1L60 44.5L57.9 36.1L50 34L57.9 31.9Z"
      fill="var(--text-05)"
    />
  </svg>
);
export default SvgEmpty;
