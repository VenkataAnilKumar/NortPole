"use client";

import type { ReactNode } from "react";
import {
  DndContext,
  DragOverlay,
  type DragStartEvent,
  type DragEndEvent,
  type CollisionDetection,
  type Modifier,
  type SensorDescriptor,
  type SensorOptions,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { WithoutStyles } from "@opal/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DraggableProps {
  dndContextProps: {
    sensors: SensorDescriptor<SensorOptions>[];
    collisionDetection: CollisionDetection;
    modifiers: Modifier[];
    onDragStart: (event: DragStartEvent) => void;
    onDragEnd: (event: DragEndEvent) => void;
    onDragCancel: () => void;
  };
  sortableItems: string[];
  activeId: string | null;
  isEnabled: boolean;
}

interface TableBodyProps extends WithoutStyles<
  React.HTMLAttributes<HTMLTableSectionElement>
> {
  ref?: React.Ref<HTMLTableSectionElement>;
}

interface TableDndProviderProps {
  /** DnD context props from useDraggableRows. Without them, or when disabled, children render as is. */
  dndSortable?: DraggableProps;
  /** Render function for the drag overlay row */
  renderDragOverlay?: (activeId: string) => ReactNode;
  children: ReactNode;
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

/**
 * Drag-and-drop context for sortable rows. It wraps the whole table, not the
 * <tbody>: the context renders <div> elements of its own (screen-reader
 * instructions, the drag overlay), which are not allowed inside a <table>.
 */
function TableDndProvider({
  dndSortable,
  renderDragOverlay,
  children,
}: TableDndProviderProps) {
  if (!dndSortable?.isEnabled) return <>{children}</>;
  const { dndContextProps, sortableItems, activeId } = dndSortable;
  return (
    <DndContext
      sensors={dndContextProps.sensors}
      collisionDetection={dndContextProps.collisionDetection}
      modifiers={dndContextProps.modifiers}
      onDragStart={dndContextProps.onDragStart}
      onDragEnd={dndContextProps.onDragEnd}
      onDragCancel={dndContextProps.onDragCancel}
    >
      <SortableContext
        items={sortableItems}
        strategy={verticalListSortingStrategy}
      >
        {children}
      </SortableContext>
      <DragOverlay dropAnimation={null}>
        {activeId && renderDragOverlay ? renderDragOverlay(activeId) : null}
      </DragOverlay>
    </DndContext>
  );
}

function TableBody({ ref, ...props }: TableBodyProps) {
  return <tbody ref={ref} {...props} />;
}

export default TableBody;
export { TableDndProvider };
export type { TableBodyProps, TableDndProviderProps, DraggableProps };
