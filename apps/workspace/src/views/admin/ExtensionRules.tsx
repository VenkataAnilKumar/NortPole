"use client";

import { ActionButton, NativeInput, NativeSelect, NativeTextArea } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState } from "react";
import useSWR, { mutate } from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Rules {
  personal_skills: "off" | "self_serve";
  mcp_allowlist_enabled: boolean;
  mcp_allowed_hosts: string[];
}
const URL = "/api/admin/extensions";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";

/** What people may add: personal skills on or off, and which hosts an MCP server may use. */
export default function ExtensionRules() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data } = useSWR<Rules>(URL, errorHandlingFetcher);
  const [skills, setSkills] = useState<"off" | "self_serve">("self_serve");
  const [enabled, setEnabled] = useState(false);
  const [hosts, setHosts] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data) {
      setSkills(data.personal_skills);
      setEnabled(data.mcp_allowlist_enabled);
      setHosts(data.mcp_allowed_hosts.join("\n"));
    }
  }, [data]);

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(URL, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          personal_skills: skills,
          mcp_allowlist_enabled: enabled,
          mcp_allowed_hosts: hosts.split(/[\s,]+/).filter(Boolean),
        }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `Could not save (HTTP ${res.status}).`);
      await mutate(URL);
      await mutate("/api/admin/inventory");
      setMsg({ ok: true, text: "Saved. It applies to the next request." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Could not save." });
    } finally {
      setBusy(false);
    }
  };

  if (!data) return null;
  return (
    <section className={card} aria-labelledby="ext-h" data-testid="extension-rules">
      <h2 id="ext-h" className="text-base font-semibold text-text-05">{workspaceText("extensionRules")}</h2>
      <p className="mt-1 text-sm text-text-03">{workspaceText("whatPeopleMayAddARequestThenAdministratorApproves")}</p>
      <label className="mt-3 flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("personalSkills_a7a520")}<NativeSelect className={input} value={skills} onChange={(e) => setSkills(e.target.value as "off" | "self_serve")}>
          <option value="self_serve">{workspaceText("selfServePeopleMayAddTheirOwn")}</option>
          <option value="off">{workspaceText("offNobodyMayAddOrChangeAPersonalSkill")}</option>
        </NativeSelect>
      </label>
      <label className="mt-3 flex min-h-10 cursor-pointer items-center gap-2 text-sm text-text-05">
        <NativeInput type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />{workspaceText("onlyAllowMcpServersOnTheseHostsAlsoStops")}</label>
      <label className="mt-2 flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("allowedHostsOnePerLineExampleComOrExample")}<NativeTextArea className={`${input} py-2`} rows={4} value={hosts} onChange={(e) => setHosts(e.target.value)} disabled={!enabled && hosts === ""} />
      </label>
      <div className="mt-3">
        <ActionButton type="button" disabled={busy} onClick={save} className="min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50">{workspaceText("saveRules")}</ActionButton>
      </div>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="extension-message">{msg.text}</p>}
    </section>
  );
}
