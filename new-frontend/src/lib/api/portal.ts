import { deleteJson, getJson, postJson } from "@/lib/api/client";
import type { TimelineRow } from "@/lib/api/people";

export interface PortalSummary {
  open_tickets: number;
  total_tickets: number;
  active_surveys: number;
  surveys_answered: number;
  last_chat_at: string | null;
  annual_leave_days: number;
  used_leave_days_ytd: number;
  leave_balance_remaining: number;
}

export async function getPortalSummary(): Promise<PortalSummary | null> {
  return getJson<PortalSummary>("/api/v1/portal/me/summary");
}

export interface PortalProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  employee_id?: string | null;
  designation?: string | null;
  department: string;
  manager_name?: string | null;
  joined_at?: string | null;
}

export async function getPortalProfile(): Promise<PortalProfile | null> {
  return getJson<PortalProfile>("/api/v1/portal/me/profile");
}

export interface ChatPreview {
  id: string;
  title: string;
  preview: string;
  when: string;
}

export async function getPortalChats(): Promise<ChatPreview[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/portal/me/chats");
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    title: String(row.title ?? ""),
    preview: String(row.preview ?? ""),
    when: String(row.when ?? ""),
  }));
}

export async function getPortalTimeline(): Promise<TimelineRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/portal/me/timeline");
  if (!rows) return [];
  return rows.map((row) => ({
    date: String(row.date ?? ""),
    text: String(row.text ?? ""),
    tone: String(row.tone ?? "neutral"),
  }));
}

export interface ReminderRow {
  id: string;
  reminder_type: string;
  title: string;
  message: string;
  schedule_kind: string;
  run_at: string | null;
  status: string;
  next_trigger_at: string | null;
  created_at: string;
}

export async function getMyReminders(): Promise<ReminderRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/wellbeing/reminders");
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    reminder_type: String(row.reminder_type ?? "custom"),
    title: String(row.title ?? ""),
    message: String(row.message ?? ""),
    schedule_kind: String(row.schedule_kind ?? "one_time"),
    run_at: row.run_at ? String(row.run_at) : null,
    status: String(row.status ?? "active"),
    next_trigger_at: row.next_trigger_at ? String(row.next_trigger_at) : null,
    created_at: String(row.created_at ?? ""),
  }));
}

export async function cancelReminder(reminderId: string): Promise<boolean> {
  const row = await deleteJson<Record<string, unknown>>(`/api/v1/wellbeing/reminders/${reminderId}`);
  return Boolean(row !== null);
}

export interface MoodTrend {
  average_score: number | null;
  trend: string;
  total_entries: number;
  oldest_entry?: string | null;
  newest_entry?: string | null;
}

export async function getMyMoodTrend(userId: string): Promise<MoodTrend | null> {
  return getJson<MoodTrend>(`/api/v1/mood/${userId}/trend`);
}

export async function logMyMood(input: { moodEmoji: "🙂" | "😐" | "😟" | "😔"; moodScore: number; note?: string }): Promise<boolean> {
  const row = await postJson<Record<string, unknown>>("/api/v1/mood", {
    mood_emoji: input.moodEmoji,
    mood_score: input.moodScore,
    note: input.note?.trim() || null,
  });
  return Boolean(row);
}
