"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NavLink } from "@opal/navigation";
import { useTranslations } from "next-intl";
import useUserSkills from "@/hooks/useUserSkills";
import { card, titleCase } from "@/sections/sources/shared";

export default function BuiltInSkills() {
  const t = useTranslations("workspaceUi");
  const { data, error, isLoading } = useUserSkills();
  const skills = [...(data?.builtins ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name),
  );

  return (
    <section aria-labelledby="built-in-skills" className="flex flex-col gap-3">
      <h2 id="built-in-skills" className="text-xl font-semibold text-text-05">
        {t("builtInSkills.title")}
      </h2>
      {isLoading && <p role="status" className="text-sm text-text-03">{t("loadingSkills")}</p>}
      {error && (
        <p role="alert" className="text-sm text-status-text-error-05">
          {t("skillsCouldNotBeLoadedTryAgainInA")}
        </p>
      )}
      {data && skills.length === 0 && (
        <p className="text-sm text-text-03">{t("builtInSkills.empty")}</p>
      )}
      {skills.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {skills.map((skill) => {
            const app = skill.external_app;
            const needsSetup = skill.is_available === false || (app && !app.ready);
            const status = needsSetup ? "needsSetup" : skill.enabled ? "available" : "off";
            const name = app?.name ?? (skill.name === "pptx" ? "PowerPoint" : titleCase(skill.name));

            return (
              <li key={skill.id} className={card}>
                <ResponsiveLayout display="flex" className="flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-base font-semibold text-text-05">{name}</h3>
                  <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04">
                    {t(`builtInSkills.${status}`)}
                  </span>
                </ResponsiveLayout>
                <p className="mt-2 text-sm text-text-04">{skill.description}</p>
                {skill.is_available === false && skill.unavailable_reason && (
                  <p className="mt-2 text-sm text-text-03">{skill.unavailable_reason}</p>
                )}
                {app && (
                  <NavLink
                    href={`/app/sources/integrations?integration=${encodeURIComponent(skill.name)}`}
                    className="mt-2 inline-block text-sm font-semibold text-text-05 underline"
                  >
                    {t("builtInSkills.viewIntegration", { name: app.name })}
                  </NavLink>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
