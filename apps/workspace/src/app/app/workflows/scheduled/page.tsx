import { Suspense } from "react";
import ScheduledPage from "@/sections/workflows/ScheduledPage";

export default function Page() {
  // The page reads its query (?pack=&template= or ?task=) to open the form for a workflow or a draft.
  return (
    <Suspense>
      <ScheduledPage />
    </Suspense>
  );
}
