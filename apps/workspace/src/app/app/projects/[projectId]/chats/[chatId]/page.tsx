"use client";

import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useParams } from "@opal/navigation";
import { NavLink } from "@opal/navigation";
import useSWR from "swr";
import { Button } from "@opal/components";

type Message = { id: number; role: "user" | "assistant"; text: string };
type Transcript = { title: string | null; messages: Message[]; has_older: boolean };

async function readTranscript(path: string): Promise<Transcript> {
  const result = await fetch(path, { cache: "no-store" });
  if (!result.ok) throw new Error("This project chat is unavailable.");
  return result.json();
}

export default function ProjectChatPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { projectId, chatId } = useParams<{ projectId: string; chatId: string }>();
  const key = `/api/user/projects/${encodeURIComponent(projectId)}/chats/${encodeURIComponent(chatId)}`;
  const { data, error } = useSWR(key, readTranscript, { refreshInterval: 30000 });
  const [earlier, setEarlier] = useState<Message[]>([]);
  const [hasOlder, setHasOlder] = useState<boolean | undefined>();
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setEarlier([]);
    setHasOlder(undefined);
    setFailed(false);
  }, [key]);
  const messages = [...earlier, ...(data?.messages ?? [])];
  const loadOlder = async () => {
    const before = messages[0]?.id;
    if (!before) return;
    setLoading(true);
    setFailed(false);
    try {
      const previous = await readTranscript(`${key}?before=${before}`);
      setEarlier([...previous.messages, ...earlier]);
      setHasOlder(previous.has_older);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex h-full w-full max-w-3xl flex-col gap-5 overflow-y-auto p-5 sm:p-9">
      <NavLink className="self-start text-sm text-text-03 underline" href={`/app?projectId=${encodeURIComponent(projectId)}`}>{workspaceText("backToProject")}</NavLink>
      {error ? (
        <p role="alert" className="text-text-05">{workspaceText("thisProjectChatIsUnavailable")}</p>
      ) : !data ? (
        <p role="status" className="text-text-03">{workspaceText("loadingChat")}</p>
      ) : (
        <>
          <header>
            <h1 className="break-words text-2xl font-semibold text-text-05">{data.title || "Project chat"}</h1>
            <p className="mt-1 text-sm text-text-03">{workspaceText("readOnlyTranscript")}</p>
          </header>
          {(hasOlder ?? data.has_older) && (
            <Button prominence="secondary" disabled={loading} onClick={() => void loadOlder()}>{workspaceText("loadOlderMessages")}</Button>
          )}
          {failed && <p role="alert" className="text-text-03">{workspaceText("olderMessagesCouldNotBeLoaded")}</p>}
          {messages.length === 0 && <p className="text-text-03">{workspaceText("thisChatHasNoMessages")}</p>}
          {messages.map(({ id, role, text }) => (
            <article className="rounded-xl border border-border-01 bg-background-neutral-00 p-4" key={id}>
              <h2 className="mb-2 text-sm font-semibold text-text-05">{role === "user" ? "Author" : "Assistant"}</h2>
              <p className="whitespace-pre-wrap break-words text-sm text-text-05">{text}</p>
            </article>
          ))}
        </>
      )}
    </main>
  );
}
