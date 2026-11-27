"use client";

import React from "react";
import { toast } from "@opal/layouts";
import { ChatSession } from "@/app/app/types";

/** Parameters shared by move-operation helpers. */
export interface MoveOperationParams {
  chatSession: ChatSession;
  targetProjectId: number;
  refreshChatSessions: () => Promise<any>;
  refreshCurrentProjectDetails: () => Promise<any>;
  fetchProjects: () => Promise<any>;
  currentProjectId: number | null;
}

/** Displays a red error toast with the given message. */
export const showErrorNotification = (message: string) => {
  toast.error(message);
};

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Wraps matched substrings of `text` in `<span className="text-text-05">` for
 * highlighting. Unmatched segments are returned as plain strings. Returns the
 * original string unchanged when `query` is empty or produces no match.
 */
export function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;

  const escapedQuery = escapeRegex(query.trim());
  const regex = new RegExp(`(${escapedQuery})`, "gi");
  const parts = text.split(regex);

  if (parts.length === 1) return text;

  return parts.map((part, i) =>
    i % 2 === 1
      ? React.createElement("span", { key: i, className: "text-text-05" }, part)
      : React.createElement(React.Fragment, { key: i }, part)
  );
}
