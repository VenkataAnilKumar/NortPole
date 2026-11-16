"use client";

import { NavLink } from "@opal/navigation";
import { useTranslations } from "next-intl";
import { SvgNortPoleLogo } from "@opal/logos";
import { useSettings } from "@/lib/settings/hooks";
import { Text } from "@opal/components";
import "@opal/layouts/auth/styles.css";

export default function AuthFlowContainer({
  children,
  authState,
  footerContent,
}: {
  children: React.ReactNode;
  authState?: "signup" | "login" | "join";
  footerContent?: React.ReactNode;
}) {
  const t = useTranslations("auth.flowContainer");
  const { appName, logoUrl } = useSettings();
  return (
    <div className="opal-auth-root !flex-col p-4">
      <div className="opal-auth-glass dark w-full max-w-md">
        <div className="w-full flex items-start flex-col bg-background-tint-00 rounded-16 shadow-lg shadow-box-02 p-6">
          {/* logo_display_style only governs the sidebar; auth pages always show
            the logo mark (custom when uploaded, NortPole otherwise) */}
          {logoUrl ? (
            <div
              className="aspect-square rounded-full overflow-hidden relative"
              style={{ height: 44 }}
            >
              <img
                alt={t("logo.alt")}
                src={logoUrl}
                className="object-cover object-center w-full h-full"
              />
            </div>
          ) : (
            <SvgNortPoleLogo size={44} />
          )}
          <div className="w-full mt-3">{children}</div>
        </div>
      </div>
      {authState === "login" && (
        <div className="opal-auth-card-bottom-prompt text-sm mt-6 text-center w-full mainUiBody mx-auto">
          {footerContent ?? (
            <>
              <Text font="main-ui-body" color="text-03">
                {t("signupPrompt.text", { appName })}
              </Text>{" "}
              <NavLink
                href="/auth/signup"
                className="mainUiAction underline transition-colors duration-200"
              >
                {t("createAccountLink.label")}
              </NavLink>
            </>
          )}
        </div>
      )}
      {authState === "signup" && (
        <div className="opal-auth-card-bottom-prompt text-sm mt-6 text-center w-full mainUiBody mx-auto">
          {t("signinPrompt.text")}{" "}
          <NavLink
            href="/auth/login?autoRedirectToSignup=false"
            className="mainUiAction underline transition-colors duration-200"
          >
            {t("signInLink.label")}
          </NavLink>
        </div>
      )}
    </div>
  );
}
