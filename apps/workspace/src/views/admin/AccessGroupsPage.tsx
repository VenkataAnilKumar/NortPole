"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

const URL = "/api/admin/access-groups";
const USERS_URL = "/api/manage/users/accepted/all";

interface Member {
  id: string;
  email: string;
}
interface Group {
  id: number;
  name: string;
  is_default: boolean;
  members: Member[];
  sources: { cc_pair_id: number; name: string | null }[];
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

async function call(url: string, method: string, body?: unknown): Promise<void> {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `The change could not be saved (HTTP ${res.status}).`);
  }
}

function MemberPicker({
  users,
  selected,
  onChange,
  idPrefix,
}: {
  users: Member[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  idPrefix: string;
}) {
  if (users.length === 0) return <p className="text-sm text-text-03">No users yet.</p>;
  return (
    <ul className="max-h-56 overflow-y-auto rounded-xl border border-border-01">
      {users.map((u) => (
        <li key={u.id} className="border-t border-border-01 first:border-t-0">
          <label htmlFor={`${idPrefix}-${u.id}`} className="flex min-h-11 cursor-pointer items-center gap-3 px-3 text-sm text-text-05">
            <input
              id={`${idPrefix}-${u.id}`}
              type="checkbox"
              className="h-4 w-4"
              checked={selected.has(u.id)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(u.id);
                else next.delete(u.id);
                onChange(next);
              }}
            />
            {u.email}
          </label>
        </li>
      ))}
    </ul>
  );
}

function GroupCard({ group, users, onDone }: { group: Group; users: Member[]; onDone: () => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(group.name);
  const [selected, setSelected] = useState(new Set(group.members.map((m) => m.id)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readsSources = group.sources.length > 0;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onDone();
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The change could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={card} data-testid={`group-${group.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-text-05">{group.name}</h2>
          <p className="text-sm text-text-03">
            {group.members.length} {group.members.length === 1 ? "member" : "members"}
            {" · "}
            {readsSources ? `reads ${group.sources.map((s) => s.name ?? `source ${s.cc_pair_id}`).join(", ")}` : "reads no sources yet"}
          </p>
        </div>
        {group.is_default ? (
          <span className="rounded-full border border-border-01 px-2.5 py-0.5 text-xs font-medium text-text-03">Built-in role group</span>
        ) : (
          !editing && (
            <button type="button" className={secondary} onClick={() => setEditing(true)}>
              Edit
            </button>
          )
        )}
      </div>

      {editing && (
        <div className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Name
            <input className={input} value={name} disabled={readsSources} onChange={(e) => setName(e.target.value)} maxLength={80} />
          </label>
          {readsSources && (
            <p className="text-xs text-text-03">
              This group can read a source, so it cannot be renamed or deleted. Remove it from the source first.
            </p>
          )}
          <div className="text-sm font-medium text-text-05">Members</div>
          <MemberPicker users={users} selected={selected} onChange={setSelected} idPrefix={`g${group.id}`} />
          {error && <p role="alert" className="text-sm text-status-error-05">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={primary}
              disabled={busy || !name.trim()}
              onClick={() =>
                run(() =>
                  call(`${URL}/${group.id}`, "PATCH", {
                    ...(readsSources ? {} : { name }),
                    user_ids: [...selected],
                  })
                )
              }
            >
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" className={secondary} disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
            {!readsSources && (
              <button
                type="button"
                className={`${secondary} ml-auto`}
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`Delete the group "${group.name}"? Its members lose nothing else.`)) {
                    void run(() => call(`${URL}/${group.id}`, "DELETE"));
                  }
                }}
              >
                Delete group
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

/**
 * Access groups: named sets of people. A group gets to read a source when it is
 * added to that source's settings; this page only manages the groups and who is
 * in them. Removing someone takes effect on their next search.
 */
export default function AccessGroupsPage() {
  const { data: groups, error, isLoading, mutate } = useSWR<Group[]>(URL, errorHandlingFetcher);
  const { data: users } = useSWR<Member[]>(USERS_URL, errorHandlingFetcher);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState(new Set<string>());
  const [busy, setBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const people = (users ?? []).map((u) => ({ id: u.id, email: u.email })).sort((a, b) => a.email.localeCompare(b.email));

  const create = async () => {
    setBusy(true);
    setCreateError(null);
    try {
      await call(URL, "POST", { name, user_ids: [...selected] });
      setName("");
      setSelected(new Set());
      await mutate();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "The group could not be created.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-8" data-testid="access-groups-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-text-05">Groups</h1>
        <p className="text-sm text-text-03">
          Named sets of people. Add a group to a source's settings to let its members read that source. Removing
          someone from a group takes effect on their next search.
        </p>
      </header>

      <section className={card} aria-labelledby="new-group">
        <h2 id="new-group" className="mb-3 text-base font-semibold text-text-05">New group</h2>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Name
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="For example, Research" />
          </label>
          <div className="text-sm font-medium text-text-05">Members</div>
          <MemberPicker users={people} selected={selected} onChange={setSelected} idPrefix="new" />
          {createError && <p role="alert" className="text-sm text-status-error-05">{createError}</p>}
          <div>
            <button type="button" className={primary} disabled={busy || !name.trim()} onClick={create}>
              {busy ? "Creating…" : "Create group"}
            </button>
          </div>
        </div>
      </section>

      {isLoading ? (
        <p className="text-sm text-text-03">Loading groups…</p>
      ) : error ? (
        <div className={card} role="alert">
          <p className="text-sm text-text-05">Groups could not be loaded. Try again in a moment.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {(groups ?? []).map((g) => (
            <GroupCard key={`${g.id}-${g.name}-${g.members.length}`} group={g} users={people} onDone={() => mutate()} />
          ))}
        </ul>
      )}
    </div>
  );
}
