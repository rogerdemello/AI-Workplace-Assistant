export type Intent = 'general' | 'leave' | 'complaint' | 'policy';
export type Step =
  | 'start'
  | 'issue'
  | 'department'
  | 'anonymous'
  | 'startDate'
  | 'endDate'
  | 'leaveType'
  | 'policyTopic'
  | 'done';

export interface FlowState {
  intent: Intent;
  step: Step;
  conversationId?: string;
  issue?: string;
  department?: string;
  anonymous?: boolean;
  startDate?: string;
  endDate?: string;
  leaveType?: string;
  policyTopic?: string;
}

export interface ChatRecord {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

export interface ControlState {
  kind: 'date' | 'select' | 'choice' | null;
  label?: string;
  options?: string[];
  actionType?: 'intent' | 'value';
}
