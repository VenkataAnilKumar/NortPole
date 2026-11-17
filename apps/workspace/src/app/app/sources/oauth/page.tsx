import { Suspense } from "react";
import OAuthReturn from "@/sections/sources/OAuthReturn";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <OAuthReturn />
    </Suspense>
  );
}
