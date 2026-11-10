import type { IconProps } from "@opal/types";
const SvgEvolvXSILogo = ({ size, ...props }: IconProps) => (
  <svg
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <path
      d="M12 3v18M4 7l16 10M20 7L4 17"
      stroke="var(--theme-primary-05)"
      strokeWidth={2}
      strokeLinecap="round"
    />
  </svg>
);
export default SvgEvolvXSILogo;
