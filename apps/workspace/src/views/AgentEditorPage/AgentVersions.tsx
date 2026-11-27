"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useState } from "react";
import { useTranslations } from "next-intl";
import useSWR, { useSWRConfig } from "swr";
import { Button, Card, Modal } from "@opal/components";
import { toast } from "@opal/layouts";
import { parseErrorDetail } from "@/lib/agents/svc";
import { useAppPosition } from "@/lib/navigation/hooks";
import { SWR_KEYS } from "@/lib/swr-keys";
import type { FullAgent, MinimalAgent } from "@/lib/agents/types";
import AgentVerificationBadge from "@/lib/agents/components/AgentVerificationBadge";

interface AgentVersionConfiguration {
  pack_source?: { pack_id: string; version: string; agent_id: string } | null;
  pilot?: import("@/lib/agents/pilots").AgentPilotKind | null;
  name: string;
  system_prompt: string;
  task_prompt: string;
  replace_base_system_prompt: boolean;
  datetime_aware: boolean;
  document_set_ids: number[];
  search_start_date: string | null;
  model_configuration_id: number | null;
}

interface PublishedAgentVersion {
  version: number;
  configuration: AgentVersionConfiguration;
  published_at: string;
  is_active: boolean;
  withdrawn_at: string | null;
  verified_at?: string | null;
}

interface AgentTest {
  chat_id: string;
  response_id: number;
  configuration: AgentVersionConfiguration;
  tested_at: string;
  own_chat: boolean;
  matches_draft: boolean;
}

export interface AgentVersionState {
  can_publish: boolean;
  can_verify?: boolean;
  company_listed?: boolean;
  active_version: number | null;
  next_version: number;
  draft: AgentVersionConfiguration | null;
  versions: PublishedAgentVersion[];
  tests: AgentTest[];
  enrollment_blocked: boolean;
  audience: "Organization" | "Shared" | "Private";
  audience_revision: string | null;
  shared_with: string[];
}

interface PublishReview {
  kind: "publish";
  test: AgentTest;
  audience: AgentVersionState["audience"];
  audienceRevision: string;
  sharedWith: string[];
  nextVersion: number;
  activeVersion: number | null;
}

interface RestoreReview {
  kind: "restore";
  version: PublishedAgentVersion;
  activeVersion: number;
}

export function useAgentVersions(agentId?: number) {
  return useSWR<AgentVersionState>(
    agentId ? `/api/persona/${agentId}/versions` : null,
    async (path: string) => {
      const response = await fetch(path);
      if (!response.ok)
        throw new Error(await parseErrorDetail(response, "Version history could not be loaded."));
      return response.json();
    },
  );
}

export default function AgentVersions({
  agentId,
  state,
  refresh,
  libraryNames,
  hasUnsavedChanges,
}: {
  agentId: number;
  state: AgentVersionState;
  refresh: () => Promise<AgentVersionState | undefined>;
  libraryNames: ReadonlyMap<number, string>;
  hasUnsavedChanges: boolean;
}) {
  const t = useTranslations("agents.editor.versions");
  const packChat = useTranslations("agents.packChat");
  const verification = useTranslations("agents.verification");
  const { mutate } = useSWRConfig();
  const appPosition = useAppPosition();
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<PublishReview | RestoreReview | null>(null);
  const testedDraft = state.tests.find((test) => test.matches_draft);
  const canReview =
    state.can_publish && !state.enrollment_blocked && Boolean(state.audience_revision);

  function reviewTest(test: AgentTest) {
    if (!canReview || !test.matches_draft || !state.audience_revision) return;
    setReview({
      kind: "publish",
      test,
      audience: state.audience,
      audienceRevision: state.audience_revision,
      sharedWith: state.shared_with,
      nextVersion: state.next_version,
      activeVersion: state.active_version,
    });
  }

  async function refreshVersionViews() {
    const next = await refresh();
    if (!next) return;
    const active = next.versions.find((entry) => entry.is_active);
    const agentFields = {
      active_release_version: next.active_version,
      active_pilot: active?.configuration.pilot ?? null,
      company_verified_version: next.company_listed && active?.verified_at ? active.version : null,
    };
    await Promise.all([
      mutate<MinimalAgent[]>(
        SWR_KEYS.agents,
        (agents) =>
          agents?.map((agent) => (agent.id === agentId ? { ...agent, ...agentFields } : agent)),
        { revalidate: false },
      ),
      mutate<FullAgent>(
        SWR_KEYS.agent(agentId),
        (agent) => (agent ? { ...agent, ...agentFields } : agent),
        { revalidate: false },
      ),
    ]);
  }

  async function changeVersion(
    action: "publish" | "rollback",
    selection: Record<string, string | number>,
    expectedActiveVersion: number | null,
  ) {
    setBusy(true);
    try {
      const response = await fetch(`/api/persona/${agentId}/versions/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...selection, expected_active_version: expectedActiveVersion }),
      });
      if (response.status === 409) await refreshVersionViews();
      if (!response.ok) throw new Error(await parseErrorDetail(response, t("error")));
      await refreshVersionViews();
      toast.success(t("updated"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("error"));
    } finally {
      setReview(null);
      setBusy(false);
    }
  }

  function confirmReview(review: PublishReview | RestoreReview) {
    if (review.kind === "restore") {
      return changeVersion("rollback", { version: review.version.version }, review.activeVersion);
    }
    return changeVersion(
      "publish",
      {
        preview_chat_id: review.test.chat_id,
        test_response_id: review.test.response_id,
        expected_next_version: review.nextVersion,
        expected_audience_revision: review.audienceRevision,
      },
      review.activeVersion,
    );
  }

  async function changeVerification(version: number, verified: boolean) {
    if (!window.confirm(verification(verified ? "confirm" : "confirmRemove", { version }))) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/admin/persona/${agentId}/versions/verification`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version, verified }),
      });
      if (!response.ok) throw new Error(await parseErrorDetail(response, t("error")));
      await refreshVersionViews();
      toast.success(verification(verified ? "applied" : "removed"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  function configurationDetails(configuration: AgentVersionConfiguration) {
    return (
      <ResponsiveLayout display="flex" className="flex-col gap-1 break-words text-sm text-text-03">
        {configuration.pack_source && (
          <p>
            {packChat("origin", {
              pack: configuration.pack_source.pack_id,
              version: configuration.pack_source.version,
            })}
          </p>
        )}
        <p>{t("model", { model: configuration.model_configuration_id ?? "" })}</p>
        {configuration.document_set_ids.length > 0 && (
          <p>
            {t("knowledge", {
              libraries: configuration.document_set_ids
                .map((id) => libraryNames.get(id) ?? id)
                .join(", "),
            })}
          </p>
        )}
        {configuration.search_start_date && (
          <p>
            {t("cutoff", { date: new Date(configuration.search_start_date).toLocaleDateString() })}
          </p>
        )}
        {configuration.replace_base_system_prompt && <p>{t("replacesPrompt")}</p>}
        {configuration.datetime_aware && <p>{t("includesDate")}</p>}
        {configuration.system_prompt && (
          <p className="whitespace-pre-wrap">{configuration.system_prompt}</p>
        )}
        {configuration.task_prompt && (
          <p className="whitespace-pre-wrap">
            {t("reminders", { text: configuration.task_prompt })}
          </p>
        )}
      </ResponsiveLayout>
    );
  }

  return (
    <ResponsiveLayout display="flex" className="w-full flex-col gap-3">
      <Card border="solid" rounding={4} padding={4}>
        <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-3">
          <ResponsiveLayout display="flex" className="min-w-0 flex-col gap-1">
            <h2 className="font-medium text-text-05">{t("workflow.title")}</h2>
            <p role="status" className="text-sm text-text-03">
              {state.enrollment_blocked
                ? t("ineligible")
                : testedDraft
                  ? t(state.can_publish ? "workflow.ready" : "workflow.testComplete")
                  : state.tests.length > 0
                    ? t("workflow.retest")
                    : state.active_version !== null && !state.draft
                      ? t("active", { version: state.active_version })
                      : t("noTests")}
            </p>
            {hasUnsavedChanges && <p className="text-sm text-text-03">{t("workflow.unsaved")}</p>}
            <p className="text-sm text-text-03">{t("audience", { audience: t(state.audience) })}</p>
          </ResponsiveLayout>
          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
            <Button
              type="button"
              prominence="tertiary"
              disabled={busy}
              onClick={() => void refreshVersionViews()}
            >
              {t("refresh")}
            </Button>
            {canReview && testedDraft && (
              <Button
                type="button"
                prominence="secondary"
                disabled={busy}
                onClick={() => reviewTest(testedDraft)}
              >
                {t("workflow.review")}
              </Button>
            )}
          </ResponsiveLayout>
        </ResponsiveLayout>
      </Card>
      <details className="w-full rounded-xl border border-border-01 px-4 py-3">
        <summary className="cursor-pointer font-medium text-text-05">
          {t("title")}{" "}
          {state.active_version !== null && (
            <span className="ml-2 font-normal text-text-03">
              {t("active", { version: state.active_version })}
            </span>
          )}
        </summary>
        <ResponsiveLayout display="flex" className="mt-3 flex-col gap-3">
          {state.tests.length === 0 && <p className="text-sm text-text-03">{t("noTests")}</p>}
          {state.tests.map((test) => (
            <details key={test.chat_id} className="rounded-lg border border-border-01 px-3 py-2">
              <summary className="cursor-pointer text-sm text-text-05">
                {t("completed", {
                  name: test.configuration.name,
                  date: new Date(test.tested_at).toLocaleString(),
                })}
              </summary>
              <ResponsiveLayout display="flex" className="mt-2 flex-col gap-2">
                {!test.matches_draft && (
                  <p className="text-sm text-text-03">{t("workflow.retest")}</p>
                )}
                {configurationDetails(test.configuration)}
                <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                  {test.own_chat && (
                    <Button
                      type="button"
                      prominence="tertiary"
                      href={appPosition.linkToChat(test.chat_id).href}
                      target="_blank"
                      rel="noopener"
                    >
                      {t("openTest")}
                    </Button>
                  )}
                  {canReview && test.matches_draft && (
                    <Button
                      type="button"
                      prominence="secondary"
                      disabled={busy}
                      onClick={() => reviewTest(test)}
                    >
                      {t("workflow.review")}
                    </Button>
                  )}
                </ResponsiveLayout>
              </ResponsiveLayout>
            </details>
          ))}
          {state.versions.map((version) => (
            <details key={version.version} className="rounded-lg border border-border-01 px-3 py-2">
              <summary className="cursor-pointer text-sm text-text-05">
                {t(version.is_active ? "active" : version.withdrawn_at ? "withdrawn" : "version", {
                  version: version.version,
                })}{" "}
                · {new Date(version.published_at).toLocaleDateString()}
              </summary>
              <ResponsiveLayout display="flex" className="mt-2 flex-col gap-2">
                {configurationDetails(version.configuration)}
                {version.verified_at && <AgentVerificationBadge version={version.version} />}
                {state.can_verify &&
                  (version.verified_at || (version.is_active && state.company_listed)) && (
                    <div>
                      <Button
                        type="button"
                        prominence="secondary"
                        disabled={busy}
                        onClick={() =>
                          void changeVerification(version.version, !version.verified_at)
                        }
                      >
                        {verification(version.verified_at ? "remove" : "verify")}
                      </Button>
                    </div>
                  )}
                {state.can_publish &&
                  state.active_version !== null &&
                  version.version < state.active_version &&
                  !version.withdrawn_at && (
                    <div>
                      <Button
                        type="button"
                        prominence="secondary"
                        disabled={busy}
                        onClick={() => {
                          if (state.active_version !== null) {
                            setReview({
                              kind: "restore",
                              version,
                              activeVersion: state.active_version,
                            });
                          }
                        }}
                      >
                        {t("rollback")}
                      </Button>
                    </div>
                  )}
              </ResponsiveLayout>
            </details>
          ))}
        </ResponsiveLayout>
      </details>
      {review && (
        <Modal
          open
          onOpenChange={(open) => {
            if (!open && !busy) setReview(null);
          }}
        >
          <Modal.Content width="lg" height="fit">
            <Modal.Header
              title={
                review.kind === "publish"
                  ? t("workflow.publishTitle", { version: review.nextVersion })
                  : t("workflow.restore.title", { version: review.version.version })
              }
            />
            <Modal.Body>
              {review.kind === "restore" ? (
                <>
                  <p>{t("workflow.restore.newChats", { version: review.version.version })}</p>
                  <p>{t("workflow.restore.existingChats", { version: review.activeVersion })}</p>
                  <p>{t("workflow.restore.access")}</p>
                  {configurationDetails(review.version.configuration)}
                </>
              ) : (
                <>
                  <p>{t("audience", { audience: t(review.audience) })}</p>
                  <p>{t(`workflow.access.${review.audience}`)}</p>
                  {review.sharedWith.length > 0 && (
                    <ul className="list-disc break-words ps-5 text-sm text-text-03">
                      {review.sharedWith.map((recipient, index) => (
                        <li key={index}>{recipient}</li>
                      ))}
                    </ul>
                  )}
                  <h3 className="font-medium text-text-05">
                    {t("completed", {
                      name: review.test.configuration.name,
                      date: new Date(review.test.tested_at).toLocaleString(),
                    })}
                  </h3>
                  {configurationDetails(review.test.configuration)}
                </>
              )}
            </Modal.Body>
            <Modal.Footer>
              <Button
                type="button"
                prominence="secondary"
                disabled={busy}
                onClick={() => setReview(null)}
              >
                {t("workflow.cancel")}
              </Button>
              <Button type="button" disabled={busy} onClick={() => void confirmReview(review)}>
                {t(review.kind === "restore" ? "rollback" : "publish")}
              </Button>
            </Modal.Footer>
          </Modal.Content>
        </Modal>
      )}
    </ResponsiveLayout>
  );
}
