import type { IconProps } from "@opal/types";
const SvgNortPoleWordmark = ({ size, ...props }: IconProps) => (
  <svg
    height={size}
    viewBox="0 0 152 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    role="img"
    aria-label="NortPole"
    {...props}
  >
    <text
      x="0"
      y="46"
      fontFamily="var(--font-brand), Inter, system-ui, sans-serif"
      fontSize="38"
      fontWeight="700"
      textLength="150"
      lengthAdjust="spacingAndGlyphs"
      fill="var(--theme-primary-05)"
    >
      NortPole
    </text>
  </svg>
);
export default SvgNortPoleWordmark;
