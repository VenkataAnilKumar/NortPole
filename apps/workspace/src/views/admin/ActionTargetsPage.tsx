"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeSelect } from "@opal/components";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

const URL = "/api/admin/action-targets";
const CLASSES = ["public", "internal", "confidential", "restricted"] as const;

interface Target {
  id: number;
  name: string;
  url: string;
  kind?: string;
  tier?: string;
  allowed_data_classes: string[];
  enabled: boolean;
  require_second_approval?: boolean;
}



/** The body the server expects when a destination is changed; every field is sent so none is reset by accident. */
const patchBody = (t: Target, changes: Partial<Target>) => ({
  name: t.name, kind: t.kind ?? "webhook", tier: t.tier ?? "act_with_approval", url: t.url,
  allowed_data_classes: t.allowed_data_classes, enabled: t.enabled, require_second_approval: !!t.require_second_approval, ...changes,
});

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

const HELD = "This change was not applied. It waits for a second administrator to approve it (Admin > Approvals).";

async function send(url: string, method: string, body: ReturnType<typeof patchBody>): Promise<string | null> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `The change could not be saved (HTTP ${res.status}).`);
  }
  return res.status === 202 ? HELD : null;
}

function ClassPicker({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  return (
    <fieldset className="flex flex-wrap gap-3">
      <legend className="mb-1 text-sm font-medium text-text-05">{workspaceText("dataClassesThisDestinationMayReceive")}</legend>
      {CLASSES.map((c) => (
        <label key={c} className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <NativeInput
            type="checkbox"
            className="h-4 w-4"
            checked={value.includes(c)}
            onChange={(e) => onChange(e.target.checked ? [...value, c] : value.filter((x) => x !== c))}
          />
          {c}
        </label>
      ))}
    </fieldset>
  );
}

/**
 * Where approved drafts may be sent. People pick from this list and cannot type
 * a destination. A draft is sent only if the workspace's data class is ticked
 * for the destination; the check runs again at send time.
 */
export default function ActionTargetsPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, error, isLoading, mutate } = useSWR<Target[]>(URL, errorHandlingFetcher);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [kind, setKind] = useState<"webhook" | "email">("webhook");
  const [tier, setTier] = useState("act_with_approval");
  const [classes, setClasses] = useState<string[]>([]);
  const [second, setSecond] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function run(fn: () => Promise<string | null | void>) {
    setBusy(true);
    setMessage(null);
    try {
      const held = await fn();
      if (held) setMessage(held);
      await mutate();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "The change could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-4xl flex-col gap-6 p-8" data-testid="action-targets-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("sendDestinations")}</h1>
        <p className="text-sm text-text-03">{workspaceText("whereAnApprovedDraftMayBeSentAddressesThat")}</p>
      </header>

      <section className={card} aria-labelledby="new-target">
        <h2 id="new-target" className="mb-3 text-base font-semibold text-text-05">{workspaceText("addADestination")}</h2>
        <ResponsiveLayout display="flex" className="flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("name")}<NativeInput className={input} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("type")}<NativeSelect className={input} value={kind} onChange={(e) => { setKind(e.target.value as "webhook" | "email"); setUrl(""); }}>
              <option value="webhook">{workspaceText("webAddressWebhook")}</option>
              <option value="email">{workspaceText("emailFixedRecipients")}</option>
            </NativeSelect>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            {kind === "email" ? "Recipients (people choosing this destination cannot change them)" : "Web address (https recommended)"}
            <NativeInput className={input} value={url} onChange={(e) => setUrl(e.target.value)} placeholder={kind === "email" ? "mailto:finance@example.com" : "https://example.com/hook"} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("howFarTheProductMayGo")}<NativeSelect className={input} value={tier} onChange={(e) => setTier(e.target.value)}>
              <option value="act_with_approval">{workspaceText("actWithApprovalPrepareApproveTheExactContentSend")}</option>
              <option value="draft_only">{workspaceText("draftOnlyPrepareAndReviewButNeverApproveOr")}</option>
              <option value="read_only">{workspaceText("readOnlyNothingCanBeProposed")}</option>
            </NativeSelect>
          </label>
          <ClassPicker value={classes} onChange={setClasses} />
          <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
            <NativeInput type="checkbox" className="h-4 w-4" checked={second} onChange={(e) => setSecond(e.target.checked)} />{workspaceText("aSecondPersonMustApproveBeforeAnythingIsSent")}</label>
          {message && <p role={message === HELD ? "status" : "alert"} className={`text-sm ${message === HELD ? "text-text-05" : "text-status-text-error-05"}`}>{message}</p>}
          <div>
            <ActionButton
              type="button"
              className={primary}
              disabled={busy || !name.trim() || !url.trim()}
              onClick={() =>
                run(
                  // oxlint-disable-next-line react-doctor/no-impure-state-updater -- This callback is run by an event handler, outside React state updates.
                  async () => {
                  const held = await send(URL, "POST", { name, kind, tier, url, allowed_data_classes: classes, enabled: true, require_second_approval: second });
                  setSecond(false);
                  setName("");
                  setUrl("");
                  setClasses([]);
                  return held;
                })
              }
            >
              {busy ? "Saving…" : "Add destination"}
            </ActionButton>
          </div>
        </ResponsiveLayout>
      </section>

      <p className="text-sm text-text-03" data-testid="second-queue-link">{workspaceText("sendsWaitingForASecondApproverAreIn")}{" "}<NavLink href="/admin/approvals" className="font-semibold text-text-05 underline">{workspaceText("approvals")}</NavLink>.
      </p>


      {isLoading ? (
        <p className="text-sm text-text-03">{workspaceText("loading")}</p>
      ) : error ? (
        <p role="alert" className="text-sm text-text-05">{workspaceText("destinationsCouldNotBeLoaded")}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {(data ?? []).map((t) => (
            <li key={t.id} className={card} data-testid="target-item">
              <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-text-05">{t.name}</h2>
                  <p className="truncate text-sm text-text-03">{t.kind === "email" ? "Email · " : ""}{t.url}</p>
                  {t.tier && t.tier !== "act_with_approval" && <p className="text-sm text-text-03" data-testid="tier-note">{t.tier === "read_only" ? "Read only" : "Draft only"}</p>}
                  <p className="text-sm text-text-03">{workspaceText("mayReceive")}{" "}{t.allowed_data_classes.length ? t.allowed_data_classes.join(", ") : "nothing"}
                  </p>
                  <p className="text-sm text-text-03" data-testid="second-note">
                    {t.require_second_approval ? "A second person must approve each send." : "One approval (the owner's) is enough."}
                  </p>
                </div>
                <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                  <ActionButton
                    type="button"
                    className={secondary}
                    disabled={busy}
                    onClick={() => run(() => send(`${URL}/${t.id}`, "PATCH", patchBody(t, { require_second_approval: !t.require_second_approval })))}
                  >
                    {t.require_second_approval ? "Stop requiring a second approver" : "Require a second approver"}
                  </ActionButton>
                  <ActionButton
                    type="button"
                    className={secondary}
                    disabled={busy}
                    onClick={() => run(() => send(`${URL}/${t.id}`, "PATCH", patchBody(t, { enabled: !t.enabled })))}
                  >
                    {t.enabled ? "Disable" : "Enable"}
                  </ActionButton>
                </ResponsiveLayout>
              </ResponsiveLayout>
              {!t.enabled && <p className="mt-2 text-xs text-text-03">{workspaceText("disabledNothingCanBeSentHere")}</p>}
            </li>
          ))}
        </ul>
      )}
    </ResponsiveLayout>
  );
}
