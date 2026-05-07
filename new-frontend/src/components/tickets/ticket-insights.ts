import type { Ticket } from "@/lib/domain-types";

export type TicketDetailView = Ticket & {
  aiInsight: string;
  suggestedActions: string[];
  priorityReason: string;
  slaAction: string | null;
  tags: string[];
  duplicateCount: number;
  employeeSnapshot: {
    sentimentLabel: string;
    riskLabel: string;
    lastActive: string;
    openTickets: number;
  };
  thread: Array<{ by: "employee" | "mark"; text: string }>;
  timeline: string[];
};

export function buildTicketDetailView(tickets: Ticket[]): TicketDetailView[] {
  const openCountByUser: Record<string, number> = {};
  tickets.forEach((t) => {
    if (t.status !== "resolved") {
      const k = t.raisedBy || "";
      openCountByUser[k] = (openCountByUser[k] || 0) + 1;
    }
  });

  return tickets.map((ticket) => {
    const sentiment = classifySentiment(ticket);
    const ticketWords = new Set(ticket.summary.toLowerCase().split(/\W+/).filter(Boolean));
    const duplicateCount = tickets.filter((other) => {
      if (other.id === ticket.id) return false;
      const otherWords = other.summary.toLowerCase().split(/\W+/).filter(Boolean);
      const overlap = otherWords.filter((w) => ticketWords.has(w)).length;
      return overlap >= 3;
    }).length;
    const actions = [
      "Schedule 1:1 with employee",
      "Reply via MARK with acknowledgement",
      "Monitor for escalation over 48h",
    ];
    if (/manager|recognition/.test(`${ticket.title} ${ticket.summary}`.toLowerCase())) {
      actions.unshift("Notify manager's manager");
    }
    const timeline = [
      `Ticket created · ${ticket.createdAt}`,
      ticket.status === "open" ? "No response yet · action pending" : `Moved to ${ticket.status.replace("_", " ")}`,
      ticket.slaRemainingHours < 12 ? `SLA warning · ${ticket.slaRemainingHours}h left` : `SLA healthy · ${ticket.slaRemainingHours}h left`,
    ];
    return {
      ...ticket,
      aiInsight: aiInsightFor(ticket),
      suggestedActions: actions,
      priorityReason: priorityReason(ticket),
      slaAction: ticket.slaRemainingHours < 12 ? "SLA at risk — escalate now or reassign." : null,
      tags: buildTags(ticket),
      duplicateCount,
      employeeSnapshot: {
        sentimentLabel: sentiment.label,
        riskLabel: ticket.priority === "urgent" || ticket.priority === "high" ? "High" : ticket.priority === "medium" ? "Medium" : "Low",
        lastActive: "2 hours ago",
        openTickets: openCountByUser[ticket.raisedBy || ""] || 1,
      },
      thread: [
        { by: "employee", text: ticket.summary || ticket.title },
        { by: "mark", text: "Thanks for sharing this — I can route this to HR and track the response for you." },
      ],
      timeline,
    };
  });
}

function classifySentiment(ticket: Ticket): { label: string } {
  const text = `${ticket.title} ${ticket.summary}`.toLowerCase();
  if (/(not giving credit|manager|not supporting|ignored|stress|frustrat|conflict)/.test(text)) return { label: "32% ↓" };
  if (/leave|policy|timesheet/.test(text)) return { label: "58% ↔" };
  return { label: "71% ↑" };
}

function buildTags(ticket: Ticket): string[] {
  const text = `${ticket.title} ${ticket.summary}`.toLowerCase();
  const tags = new Set<string>();
  if (/manager|credit|recognition/.test(text)) tags.add("#manager_issue");
  if (/recognition|credit/.test(text)) tags.add("#recognition");
  if (/team|conflict|not listening/.test(text)) tags.add("#team_conflict");
  if (/leave|vacation|pto/.test(text)) tags.add("#leave_request");
  if (/policy|handbook|benefit/.test(text)) tags.add("#policy");
  if (/timesheet|hours/.test(text)) tags.add("#timesheet");
  if (!tags.size) tags.add(`#${ticket.category}`);
  return Array.from(tags).slice(0, 4);
}

function priorityReason(ticket: Ticket): string {
  if (ticket.priority === "urgent") return "due to severe employee impact + escalation risk";
  if (ticket.priority === "high") return "due to negative sentiment + manager/people concern";
  if (ticket.priority === "medium") return "due to employee dependency and SLA window";
  return "routine issue with low urgency indicators";
}

function aiInsightFor(ticket: Ticket): string {
  const text = `${ticket.title} ${ticket.summary}`.toLowerCase();
  if (/manager|credit|recognition/.test(text)) {
    return "Repeated concern around manager recognition behavior. Sentiment appears to be dropping; recommend direct intervention and manager coaching.";
  }
  if (/leave/.test(text)) return "Leave-related friction detected. Fast resolution improves trust and prevents repeat queries in chat.";
  if (/policy|benefit/.test(text)) return "Policy clarity issue detected. Suggest sharing canonical policy snippet and adding proactive FAQ guidance.";
  return "Employee needs a clear, timely response. A direct action + short confirmation message should resolve this quickly.";
}
