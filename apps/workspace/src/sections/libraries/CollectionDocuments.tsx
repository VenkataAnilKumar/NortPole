"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState } from "react";
import useSWR from "swr";
import { Button } from "@opal/components";
import { SvgFileText } from "@opal/icons";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { transformLinkUri } from "@/lib/utils";

interface DocumentPage {
  documents: { id: string; title: string; link: string | null; updated_at: string | null }[];
  next_cursor: string | null;
}

export default function CollectionDocuments({ collectionId }: { collectionId: number }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [cursors, setCursors] = useState<string[]>([]);
  const cursor = cursors.at(-1);
  const query = cursor ? `?${new URLSearchParams({ cursor })}` : "";
  const { data, error, mutate } = useSWR<DocumentPage>(
    `/api/manage/document-set/${collectionId}/documents${query}`,
    errorHandlingFetcher,
  );
  const nextCursor = data?.next_cursor;
  return (
    <section aria-labelledby="collection-documents" className="flex flex-col gap-3">
      <h3 id="collection-documents" className="font-semibold text-text-05">{workspaceText("documents")}</h3>
      {error ? (
        <ResponsiveLayout display="flex" className="flex-wrap items-center gap-3">
          <p role="alert" className="text-sm text-text-03">{workspaceText("couldNotLoadDocuments")}</p>
          <Button prominence="secondary" onClick={() => void mutate()}>{workspaceText("tryAgain")}</Button>
        </ResponsiveLayout>
      ) : !data ? (
        <p role="status" className="text-sm text-text-03">{workspaceText("loadingDocuments")}</p>
      ) : data.documents.length ? (
        <ul className="divide-y divide-border-01 rounded-xl border border-border-01">
          {data.documents.map((document) => {
            const link = document.link && transformLinkUri(document.link);
            return (
              <li key={document.id} className="flex items-start gap-3 px-3 py-3 text-sm">
                <SvgFileText size={18} className="mt-0.5 shrink-0 text-text-03" />
                <div className="min-w-0 break-words">
                  {link ? (
                    <a
                      href={link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-text-05 underline decoration-border-01 underline-offset-4 hover:decoration-current"
                    >
                      {document.title}
                    </a>
                  ) : (
                    <span className="font-medium text-text-05">{document.title}</span>
                  )}
                  {document.updated_at && (
                    <p className="mt-1 text-xs text-text-03">{workspaceText("updated")}{" "}
                      <time dateTime={document.updated_at}>
                        {new Date(document.updated_at).toLocaleDateString()}
                      </time>
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-text-03">{workspaceText("noAccessibleDocumentsOnThisPage")}</p>
      )}
      {(cursor || nextCursor) && (
        <ResponsiveLayout display="flex" className="gap-2">
          <Button
            prominence="secondary"
            disabled={!cursor}
            onClick={() => setCursors((previous) => previous.slice(0, -1))}
          >{workspaceText("previous")}</Button>
          <Button
            prominence="secondary"
            disabled={!nextCursor}
            onClick={() => nextCursor && setCursors((previous) => [...previous, nextCursor])}
          >{workspaceText("next")}</Button>
        </ResponsiveLayout>
      )}
    </section>
  );
}
