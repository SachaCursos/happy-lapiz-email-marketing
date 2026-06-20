import AutomationFormClient from "../../new/AutomationFormClient";

export default function EditAutomationPage({ params }: { params: { id: string } }) {
  return <AutomationFormClient editId={Number(params.id)} />;
}
