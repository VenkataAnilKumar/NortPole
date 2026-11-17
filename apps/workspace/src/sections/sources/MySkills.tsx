"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { createCustomSkillFromEditor, deleteUserSkill, isSkillNameConflict, setSkillEnabled } from "@/lib/skills/api";
import type { SkillsList } from "@/lib/skills/types";
import { card } from "@/sections/sources/shared";
import { primary, secondary } from "@/sections/sources/integrations";

export const SKILLS_URL = "/api/skills";
const field = "min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";

/** The person's own skills: add one, turn it on or off, delete it. Sharing and editing stay in the skill's own settings. */
export default function MySkills() {
  const { data, error, mutate } = useSWR<SkillsList>(SKILLS_URL, errorHandlingFetcher);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const mine = (data?.customs ?? []).filter((s) => s.user_permission === "OWNER");

  const act = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: done });
      await mutate();
    } catch (e) {
      setMsg({ ok: false, text: isSkillNameConflict(e) ? "You already have a skill with that name." : e instanceof Error ? e.message : "The request failed." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-3" aria-labelledby="my-skills" data-testid="my-skills">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="my-skills" className="text-xl font-semibold text-text-05">My skills</h2>
        {!adding && <button type="button" className={primary} onClick={() => { setAdding(true); setMsg(null); }}>Add skill</button>}
      </div>
      <p className="text-sm text-text-03">Instructions you give your own chats to follow. Only you see them until you share one. Integrations suggest skills too: open one in Discover.</p>
      {adding && (
        <form
          className={`${card} flex flex-col gap-3`}
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              await createCustomSkillFromEditor({ name: name.trim(), description: description.trim(), instructions_markdown: instructions.trim(), auto_enable: true });
              setAdding(false); setName(""); setDescription(""); setInstructions("");
            }, "Skill added and turned on.");
          }}
        >
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">Name
            <input className={field} value={name} onChange={(e) => setName(e.target.value)} maxLength={64} required placeholder="weekly-report" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">What it is for
            <input className={field} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} required />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">Instructions
            <textarea className={`${field} min-h-40 py-2`} value={instructions} onChange={(e) => setInstructions(e.target.value)} required />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={primary} disabled={busy || !name.trim() || !description.trim() || !instructions.trim()}>Save skill</button>
            <button type="button" className={secondary} onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </form>
      )}
      <p role={msg?.ok === false ? "alert" : "status"} className={`min-h-5 text-sm ${msg?.ok === false ? "text-status-text-error-05" : "text-text-05"}`}>{msg?.text ?? ""}</p>
      {error && <p role="alert" className="text-sm text-status-text-error-05">Your skills could not be loaded. Try again in a moment.</p>}
      {data && mine.length === 0 && !adding && <p className="text-sm text-text-03" data-testid="no-skills">You have no skills yet. Add one, or add a suggested one from an integration in Discover.</p>}
      {mine.length > 0 && (
        <ul className="flex flex-col divide-y divide-border-01">
          {mine.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-3" data-testid="my-skill">
              <span className="min-w-0">
                <span className="font-medium text-text-05">{s.name}</span>
                <span className="block text-sm text-text-04">{s.description}</span>
              </span>
              <span className="flex flex-wrap gap-2">
                <button type="button" className={secondary} disabled={busy || !s.can_toggle} aria-pressed={s.enabled} aria-label={`${s.enabled ? "Turn off" : "Turn on"} ${s.name}`} onClick={() => act(() => setSkillEnabled(s.id, !s.enabled), s.enabled ? `Turned off ${s.name}.` : `Turned on ${s.name}.`)}>{s.enabled ? "On" : "Off"}</button>
                <button type="button" className={secondary} disabled={busy} aria-label={`Delete ${s.name}`} onClick={() => act(() => deleteUserSkill(s.id), `Deleted ${s.name}.`)}>Delete</button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
