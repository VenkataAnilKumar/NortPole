/** Drag-and-drop type identifiers used across the sidebar's DnD contexts. */
export const DRAG_TYPES = {
  /** A chat session being dragged (e.g. into a project folder). */
  CHAT: "chat",
  /** A project folder acting as a drop target. */
  PROJECT: "project",
  /** The Recents section acting as a drop target (removes a chat from a project). */
  RECENTS: "recents",
} as const;
