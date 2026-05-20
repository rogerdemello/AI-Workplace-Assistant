import { ensureSessionToken } from "@/lib/chat-api";
import { apiBaseUrl, extractErrorMessage, getJson, readStoredSession } from "@/lib/api/client";

export interface Room {
  id: string;
  name: string;
  capacity: number;
  location: string | null;
  facilities: string[];
  is_active: boolean;
  created_at: string;
}

export interface TimeSlot {
  start: string;
  end: string;
  available: boolean;
}

export interface AvailabilityResponse {
  room_id: string;
  date: string;
  available: boolean;
  slots: TimeSlot[];
}

export interface RoomBooking {
  id: string;
  room_id: string;
  user_id: string;
  title: string;
  start_time: string;
  end_time: string;
  created_at: string;
}

export interface RoomBookingCreate {
  room_id: string;
  title: string;
  start_time: string;
  end_time: string;
}

export async function listRooms(): Promise<Room[]> {
  const rows = await getJson<Room[]>("/api/v1/rooms");
  return Array.isArray(rows) ? rows : [];
}

export async function getRoomAvailability(
  roomId: string,
  date: string,
): Promise<AvailabilityResponse | null> {
  return getJson<AvailabilityResponse>(
    `/api/v1/rooms/${roomId}/availability?date=${encodeURIComponent(date)}`,
  );
}

export async function getMyBookings(): Promise<RoomBooking[]> {
  const rows = await getJson<RoomBooking[]>("/api/v1/rooms/bookings/my");
  return Array.isArray(rows) ? rows : [];
}

export async function bookRoom(
  body: RoomBookingCreate,
): Promise<{ ok: boolean; data?: RoomBooking; error?: string }> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return { ok: false, error: "Not authenticated" };
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/rooms/book`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const msg = await extractErrorMessage(response);
      return { ok: false, error: msg };
    }
    return { ok: true, data: (await response.json()) as RoomBooking };
  } catch {
    return { ok: false, error: "Network error" };
  }
}

export async function cancelBooking(bookingId: string): Promise<boolean> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return false;
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/rooms/bookings/${bookingId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.ok;
  } catch {
    return false;
  }
}
