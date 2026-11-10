"use client";

import { Text } from "@opal/components";
import { useTranslations } from "next-intl";
import { useSettings } from "@/lib/settings/hooks";
import { DEFAULT_LOGO_SIZE_PX } from "@/lib/constants";
import { Section } from "@opal/layouts";
import { cn } from "@opal/utils";
import { SvgEvolvXSILogo, SvgEvolvXSILogoWordmark, SvgEvolvXSIWordmark } from "@opal/logos";
import { IconProps } from "@opal/types";

export interface LogoProps extends IconProps {
  // Always render the real EvolvXSI mark, ignoring the enterprise custom logo.
  // Used by EvolvXSI-branded surfaces like Craft.
  evolvxsiBranded?: boolean;
}

/**
 * The app mark alone: the uploaded custom logo when one is set, the EvolvXSI
 * mark otherwise. Shaped like an Opal icon, so it fits any `icon` slot and
 * honours the size or style the slot passes.
 */
export function Logo({ size, className, style, evolvxsiBranded }: LogoProps) {
  const t = useTranslations("common");
  const resolvedSize = size ?? DEFAULT_LOGO_SIZE_PX;
  const { logoUrl } = useSettings();

  if (evolvxsiBranded || !logoUrl) {
    return (
      <SvgEvolvXSILogo
        size={resolvedSize}
        className={cn("shrink-0", className)}
        style={style}
      />
    );
  }

  return (
    <div
      className={cn(
        "aspect-square rounded-full overflow-hidden relative shrink-0",
        className
      )}
      style={{ height: resolvedSize, ...style }}
    >
      <img
        alt={t("logo.image.alt")}
        src={logoUrl}
        className="object-cover object-center w-full h-full"
      />
    </div>
  );
}

export interface FoldableLogoProps extends LogoProps {
  folded?: boolean;
}

/**
 * The sidebar's brand block: the mark, and when unfolded the application
 * name and the "powered by" line beside it, per the enterprise display style.
 */
export function FoldableLogo({
  folded,
  size,
  className,
  evolvxsiBranded,
}: FoldableLogoProps) {
  const t = useTranslations("common");
  const resolvedSize = size ?? DEFAULT_LOGO_SIZE_PX;
  const { enterprise, logoUrl, hide_evolvxsi_branding, isLoading } = useSettings();
  const logoDisplayStyle = enterprise?.logo_display_style;
  const applicationName = enterprise?.application_name;

  if (evolvxsiBranded) {
    return folded ? (
      <Logo evolvxsiBranded size={resolvedSize} className={className} />
    ) : (
      <SvgEvolvXSILogoWordmark size={resolvedSize} className={className} />
    );
  }

  const logo = <Logo size={resolvedSize} className={className} />;

  const renderNameAndPoweredBy = (opts: {
    includeLogo: boolean;
    includeName: boolean;
  }) => {
    return (
      <div className="flex min-w-0 gap-2">
        {opts.includeLogo && logo}
        {!folded && (
          /* H3 text is 4px larger (28px) than the Logo icon (24px), so negative margin hack. */
          <div className="flex flex-1 flex-col -mt-0.5">
            {opts.includeName && (
              <Text
                maxLines={1}
                overflowTooltip
                as="p"
                textPosition="text-start"
                font="heading-section"
                color="text-05"
              >
                {applicationName ?? ""}
              </Text>
            )}
            {/* Wait for settings so a hidden tagline never flashes. */}
            {!isLoading && !hide_evolvxsi_branding && (
              <Text font="secondary-body" color="text-03" maxLines={1}>
                {t("logo.poweredBy.label")}
              </Text>
            )}
          </div>
        )}
      </div>
    );
  };

  // No custom name: the EvolvXSI wordmark beside the mark, which a custom logo
  // overrides.
  if (!applicationName) {
    if (folded) return <Logo size={resolvedSize} className={className} />;
    if (!logoUrl) {
      return <SvgEvolvXSILogoWordmark size={resolvedSize} className={className} />;
    }
    return (
      <Section
        flexDirection="row"
        alignItems="center"
        justifyContent="start"
        gap={2}
        width="fit"
        height="fit"
      >
        <Logo size={resolvedSize} className={className} />
        <SvgEvolvXSIWordmark size={resolvedSize} />
      </Section>
    );
  }

  // A custom name, with the custom logo or the EvolvXSI mark. The display style
  // can leave out either one.
  return renderNameAndPoweredBy({
    includeLogo: logoDisplayStyle !== "name_only",
    includeName: logoDisplayStyle !== "logo_only",
  });
}

/**
 * The sidebar's logo mark: the workspace's custom logo, or the EvolvXSI mark.
 * Renders nothing when a workspace with a custom name shows the name only.
 */
export function SidebarLogoMark({ size }: { size: number }) {
  const { enterprise } = useSettings();
  if (
    enterprise?.application_name &&
    enterprise.logo_display_style === "name_only"
  ) {
    return null;
  }
  return <Logo size={size} />;
}

/**
 * The sidebar's wordmark, beside the mark: the custom name, which overrides
 * the EvolvXSI wordmark, with the "Powered by" line unless EvolvXSI branding is
 * hidden. Without a custom name, the EvolvXSI wordmark.
 */
export function SidebarWordmark({ size }: { size: number }) {
  const t = useTranslations("common");
  const { enterprise, hide_evolvxsi_branding, isLoading } = useSettings();
  const logoDisplayStyle = enterprise?.logo_display_style;
  const applicationName = enterprise?.application_name;

  if (!applicationName) {
    return <SvgEvolvXSIWordmark size={size} />;
  }

  return (
    /* The name's line is as tall as the 28px mark, so the two sit level; the
    "Powered by" line hangs below and never moves the name. */
    <Section
      flexDirection="column"
      alignItems="start"
      justifyContent="start"
      gap={0}
      height="fit"
      className="min-w-0 flex-1"
    >
      {logoDisplayStyle !== "logo_only" && (
        <Text
          maxLines={1}
          overflowTooltip
          as="p"
          textPosition="text-start"
          font="heading-section"
          color="text-05"
        >
          {applicationName}
        </Text>
      )}
      {/* Wait for settings so a hidden tagline never flashes. */}
      {!isLoading && !hide_evolvxsi_branding && (
        <Text font="secondary-body" color="text-03" maxLines={1}>
          {t("logo.poweredBy.label")}
        </Text>
      )}
    </Section>
  );
}
