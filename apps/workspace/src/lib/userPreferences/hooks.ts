"use client";

import useSWR, { mutate } from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

export type DefaultRoute = "auto" | "local" | "private" | "cloud";

export interface QuietHours {
  enabled: boolean;
  start: string;
  end: string;
}

export interface UserPreferences {
  default_route: DefaultRoute;
  notifications: {
    approvals: boolean;
    run_updates: boolean;
    quiet_hours: QuietHours;
  };
}

export const USER_PREFERENCES_URL = "/api/user-preferences";

/** The signed-in person's own preferences, kept on the server so they follow the person across devices. */
export function useUserPreferences() {
  return useSWR<UserPreferences>(USER_PREFERENCES_URL, errorHandlingFetcher);
}

/**
 * Save the whole record. The screen updates at once and is rolled back if the
 * server refuses. Throws on failure so the caller can say so.
 */
export async function saveUserPreferences(prefs: UserPreferences): Promise<UserPreferences> {
  await mutate(USER_PREFERENCES_URL, prefs, { revalidate: false });
  try {
    const res = await fetch(USER_PREFERENCES_URL, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
    if (!res.ok) throw new Error(`Could not save preferences (HTTP ${res.status})`);
    const saved = (await res.json()) as UserPreferences;
    await mutate(USER_PREFERENCES_URL, saved, { revalidate: false });
    return saved;
  } catch (e) {
    await mutate(USER_PREFERENCES_URL);
    throw e;
  }
}
