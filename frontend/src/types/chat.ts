export type Intent = "general" | "leave" | "complaint" | "policy";

export type Step =
  | "start"
  | "issue"
  | "targetPerson"
  | "details"
  | "department"
  | "anonymous"
  | "startDate"
  | "endDate"
  | "leaveType"
  | "leaveReason"
  | "policyTopic"
  | "done";

export interface FlowState {
  intent: Intent;
  step: Step;
  conversationId?: string;
  issue?: string;
  targetPerson?: string;
  details?: string;
  department?: string;
  anonymous?: boolean;
  startDate?: string;
  endDate?: string;
  leaveType?: string;
  leaveReason?: string;
  policyTopic?: string;
}

export interface ChatRecord {
  id: string;
  role: "user" | "assistant";
  text: string;
}

export interface ControlState {
  kind: "date" | "select" | "choice" | null;
  label?: string;
  options?: string[];
}

export interface MemoryCard {
  title: string;
  summary: string;
  tags: string[];
  lastUpdated: string;
}

/** Mirrors backend `/api/v1/chat/message` flow_metadata. */
export interface FlowMetadata {
  flow_name: string | null;
  intent?: string | null;
  step?: string | null;
  missing_fields: string[];
  collected_fields: string[];
  completed: boolean;
}

