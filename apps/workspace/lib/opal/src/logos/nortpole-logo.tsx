import type { IconProps } from "@opal/types";
const SvgNortPoleLogo = ({ size, ...props }: IconProps) => (
  <svg
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    {/* The North Star: a four-point guiding star (decision 0007). */}
    <path
      d="M12 1.5 L14.1 9.9 L22 12 L14.1 14.1 L12 22.5 L9.9 14.1 L2 12 L9.9 9.9 Z"
      fill="var(--theme-primary-05)"
    />
  </svg>
);
export default SvgNortPoleLogo;
