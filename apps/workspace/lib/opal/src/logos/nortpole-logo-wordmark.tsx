import SvgNortPoleLogo from "@opal/logos/nortpole-logo";
import SvgNortPoleWordmark from "@opal/logos/nortpole-wordmark";
import { cn } from "@opal/utils";

interface NortPoleLogoWordmarkProps {
  size?: number;
  className?: string;
}

// # NOTE(@raunakab):
// This ratio is not some random, magical number; it is available on Figma.
const HEIGHT_TO_GAP_RATIO = 5 / 16;

const SvgNortPoleLogoWordmark = ({
  size: height,
  className,
}: NortPoleLogoWordmarkProps) => {
  const gap = height != null ? height * HEIGHT_TO_GAP_RATIO : undefined;

  return (
    <div
      className={cn(`flex flex-row items-center`, className)}
      style={{ gap }}
    >
      <SvgNortPoleLogo size={height} />
      <SvgNortPoleWordmark size={height} />
    </div>
  );
};
export default SvgNortPoleLogoWordmark;
