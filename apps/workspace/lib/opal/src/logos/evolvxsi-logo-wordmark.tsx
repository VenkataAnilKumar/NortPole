import SvgEvolvXSILogo from "@opal/logos/evolvxsi-logo";
import SvgEvolvXSIWordmark from "@opal/logos/evolvxsi-wordmark";
import { cn } from "@opal/utils";

interface EvolvXSILogoWordmarkProps {
  size?: number;
  className?: string;
}

// # NOTE(@raunakab):
// This ratio is not some random, magical number; it is available on Figma.
const HEIGHT_TO_GAP_RATIO = 5 / 16;

const SvgEvolvXSILogoWordmark = ({
  size: height,
  className,
}: EvolvXSILogoWordmarkProps) => {
  const gap = height != null ? height * HEIGHT_TO_GAP_RATIO : undefined;

  return (
    <div
      className={cn(`flex flex-row items-center`, className)}
      style={{ gap }}
    >
      <SvgEvolvXSILogo size={height} />
      <SvgEvolvXSIWordmark size={height} />
    </div>
  );
};
export default SvgEvolvXSILogoWordmark;
