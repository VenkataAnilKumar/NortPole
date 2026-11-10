import type { IconProps } from "@opal/types";

const SvgEvolvXSIOctagon = ({ size, ...props }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    stroke="currentColor"
    {...props}
  >
    <rect
      x="1.75"
      y="1.75"
      width="12.5"
      height="12.5"
      rx="3.5"
      strokeWidth={1.5}
      strokeLinejoin="round"
    />
  </svg>
);
export default SvgEvolvXSIOctagon;
