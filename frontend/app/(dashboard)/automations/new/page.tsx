import { Suspense } from "react";
import AutomationFormClient from "./AutomationFormClient";

export const dynamic = "force-dynamic";

export default function NewAutomationPage() {
  return (
    <Suspense>
      <AutomationFormClient />
    </Suspense>
  );
}
