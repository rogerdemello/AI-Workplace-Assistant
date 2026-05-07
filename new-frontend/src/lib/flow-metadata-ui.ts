import type { ControlState, FlowMetadata } from "@/types/chat";

/** Map backend `flow_metadata` to in-panel controls (chips, date, yes/no). */
export function mapFlowMetadataToControl(meta: FlowMetadata | null | undefined): ControlState {
  if (!meta?.flow_name || meta.completed) {
    return { kind: null };
  }
  const step = meta.step || "";

  if (meta.flow_name === "leave_request") {
    if (step === "leave_type") {
      return {
        kind: "select",
        label: "Leave type",
        options: ["paid", "sick", "work from home", "unpaid"],
      };
    }
    if (step === "start_date" || step === "end_date") {
      return { kind: "date", label: step === "start_date" ? "Start date" : "End date" };
    }
  }

  if (meta.flow_name === "ticket") {
    if (step === "severity") {
      return { kind: "select", label: "Severity", options: ["mild", "serious", "urgent"] };
    }
    if (step === "department") {
      return {
        kind: "select",
        label: "Department",
        options: ["HR", "IT", "Facilities", "Finance", "Management"],
      };
    }
    if (step === "anonymous") {
      return { kind: "choice", label: "Stay anonymous?" };
    }
  }

  return { kind: null };
}

export function formatFlowStepLabel(meta: FlowMetadata | null | undefined): string | null {
  if (!meta?.flow_name || meta.completed) return null;
  const name = meta.flow_name === "leave_request" ? "Leave" : meta.flow_name === "ticket" ? "Ticket" : meta.flow_name;
  const step = meta.step ? meta.step.replace(/_/g, " ") : "in progress";
  return `${name} · ${step}`;
}
