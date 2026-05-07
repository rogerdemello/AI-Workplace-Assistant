export type TicketStatus = "open" | "in_progress" | "resolved" | "escalated";
export type Priority = "low" | "medium" | "high" | "urgent";
export type Sentiment = "positive" | "neutral" | "watch" | "at_risk";

export interface Employee {
  id: string;
  name: string;
  role: string;
  department: string;
  email: string;
  initials: string;
  joinedAt: string;
  sentiment: Sentiment;
  sentimentScore?: number;
  sentimentTrend?: "up" | "down" | "stable";
  sentimentDelta?: number;
  riskScore: number;
  riskLabel?: "Low" | "Medium" | "High";
  /** Story bullets from analytics (sentiment, complaints, topic, engagement). */
  narrative?: string[];
  spikeAlert?: boolean;
  silentRisk?: boolean;
  topTopic?: string;
  topEmotion?: string;
  complaints5d?: number;
  shortTermTrend?: number;
  longTermTrend?: number;
  leaveBalance: number;
  manager?: string;
  managerId?: string;
  location: string;
}

export interface Ticket {
  id: string;
  title: string;
  summary: string;
  category: "leave" | "policy" | "complaint" | "payroll" | "it" | "wellbeing";
  status: TicketStatus;
  priority: Priority;
  raisedBy: string;
  assignedTo?: string;
  createdAt: string;
  updatedAt: string;
  slaHours: number;
  slaRemainingHours: number;
}

export interface Survey {
  id: string;
  title: string;
  audience: string;
  responses: number;
  invited: number;
  sentiment: Sentiment;
  closedAt?: string;
  status: "live" | "draft" | "closed";
}
