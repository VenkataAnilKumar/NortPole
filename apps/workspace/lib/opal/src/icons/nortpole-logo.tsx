import type { IconProps } from "@opal/types";
const SvgNortPoleLogo = ({ size, ...props }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <path
      d="M8 2v12M2.67 4.67l10.66 6.66M13.33 4.67L2.67 11.33"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);
export default SvgNortPoleLogo;
