import { useEffect, useMemo, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Users, MapPin, Clock, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import {
  bookRoom,
  cancelBooking,
  getMyBookings,
  getRoomAvailability,
  listRooms,
  type AvailabilityResponse,
  type Room,
  type RoomBooking,
} from "@/lib/api/rooms";
import { cn } from "@/lib/utils";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Rooms() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [date, setDate] = useState(todayIso());
  const [availability, setAvailability] = useState<AvailabilityResponse | null>(null);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [bookings, setBookings] = useState<RoomBooking[]>([]);
  const [title, setTitle] = useState("");
  const [pickedSlot, setPickedSlot] = useState<{ start: string; end: string } | null>(null);
  const [busy, setBusy] = useState<"idle" | "booking" | "cancelling">("idle");

  const refreshBookings = () => {
    void getMyBookings().then(setBookings);
  };

  useEffect(() => {
    void listRooms().then((rows) => {
      setRooms(rows);
      if (rows.length > 0 && selectedRoomId === null) {
        setSelectedRoomId(rows[0].id);
      }
    });
    refreshBookings();
  }, []);

  useEffect(() => {
    if (!selectedRoomId) {
      setAvailability(null);
      return;
    }
    setAvailabilityLoading(true);
    void getRoomAvailability(selectedRoomId, date)
      .then(setAvailability)
      .finally(() => setAvailabilityLoading(false));
    setPickedSlot(null);
  }, [selectedRoomId, date]);

  const selectedRoom = useMemo(
    () => rooms.find((r) => r.id === selectedRoomId) ?? null,
    [rooms, selectedRoomId],
  );

  const handleBook = async () => {
    if (!selectedRoomId || !pickedSlot || !title.trim()) return;
    const [sh, sm] = pickedSlot.start.split(":").map(Number);
    const [eh, em] = pickedSlot.end.split(":").map(Number);
    const [y, m, d] = date.split("-").map(Number);
    const start = new Date(y, m - 1, d, sh, sm, 0).toISOString();
    const end = new Date(y, m - 1, d, eh, em, 0).toISOString();

    setBusy("booking");
    const result = await bookRoom({
      room_id: selectedRoomId,
      title: title.trim(),
      start_time: start,
      end_time: end,
    });
    setBusy("idle");
    if (!result.ok) {
      toast.error(result.error || "Booking failed");
      return;
    }
    toast.success("Room booked.");
    setTitle("");
    setPickedSlot(null);
    refreshBookings();
    // Refresh availability since the slot we just claimed is now busy.
    if (selectedRoomId) {
      void getRoomAvailability(selectedRoomId, date).then(setAvailability);
    }
  };

  const handleCancel = async (bookingId: string) => {
    if (!window.confirm("Cancel this booking?")) return;
    setBusy("cancelling");
    const ok = await cancelBooking(bookingId);
    setBusy("idle");
    if (!ok) {
      toast.error("Could not cancel booking.");
      return;
    }
    toast.success("Booking cancelled.");
    refreshBookings();
    if (selectedRoomId) {
      void getRoomAvailability(selectedRoomId, date).then(setAvailability);
    }
  };

  return (
    <AppLayout title="Rooms" subtitle="Book a meeting room from the office floor plan">
      <div className="px-6 lg:px-10 py-8 max-w-6xl space-y-8">
        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
              Rooms
            </div>
            <ul className="space-y-2">
              {rooms.length === 0 && (
                <li className="text-sm text-muted-foreground">
                  No rooms configured yet. Ask an admin to add some.
                </li>
              )}
              {rooms.map((room) => (
                <li key={room.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedRoomId(room.id)}
                    className={cn(
                      "w-full text-left rounded-xl border border-border p-3 transition-colors",
                      selectedRoomId === room.id
                        ? "bg-secondary border-border"
                        : "bg-card hover:bg-secondary/60",
                    )}
                  >
                    <div className="text-sm font-medium">{room.name}</div>
                    <div className="text-[11px] text-muted-foreground mt-1 flex flex-wrap gap-2">
                      <span className="inline-flex items-center gap-1">
                        <Users className="size-3" /> {room.capacity}
                      </span>
                      {room.location && (
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="size-3" /> {room.location}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Availability
                  </div>
                  <div className="text-sm font-medium mt-0.5">
                    {selectedRoom ? selectedRoom.name : "Pick a room"}
                  </div>
                </div>
                <input
                  type="date"
                  value={date}
                  min={todayIso()}
                  onChange={(e) => setDate(e.target.value)}
                  className="text-sm px-2 py-1 rounded-md border border-border bg-card"
                />
              </div>

              {availabilityLoading ? (
                <div className="py-8 text-center text-sm text-muted-foreground">Loading…</div>
              ) : !availability || availability.slots.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  No slot data for this date.
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {availability.slots.map((slot) => {
                    const id = `${slot.start}-${slot.end}`;
                    const picked = pickedSlot?.start === slot.start && pickedSlot.end === slot.end;
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => slot.available && setPickedSlot({ start: slot.start, end: slot.end })}
                        disabled={!slot.available}
                        className={cn(
                          "rounded-lg border px-3 py-2 text-xs font-medium transition-colors",
                          !slot.available && "bg-secondary/40 text-muted-foreground border-border line-through opacity-60 cursor-not-allowed",
                          slot.available && !picked && "bg-card border-border hover:bg-secondary",
                          picked && "bg-emerald-soft text-emerald border-emerald/40",
                        )}
                      >
                        <Clock className="size-3 inline mr-1" />
                        {slot.start}–{slot.end}
                        {picked && <CheckCircle2 className="size-3 inline ml-1" />}
                      </button>
                    );
                  })}
                </div>
              )}

              {pickedSlot && (
                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Meeting title"
                    className="flex-1 px-3 py-2 rounded-lg border border-border bg-card text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => void handleBook()}
                    disabled={busy !== "idle" || !title.trim()}
                    className="px-4 py-2 rounded-lg bg-ink text-primary-foreground text-sm font-medium disabled:opacity-50"
                  >
                    {busy === "booking" ? "Booking…" : `Book ${pickedSlot.start}`}
                  </button>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
                My bookings
              </div>
              {bookings.length === 0 ? (
                <div className="text-sm text-muted-foreground py-4">
                  You have no upcoming room bookings.
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {bookings.map((b) => {
                    const room = rooms.find((r) => r.id === b.room_id);
                    const start = new Date(b.start_time);
                    const end = new Date(b.end_time);
                    return (
                      <li key={b.id} className="py-3 flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium">{b.title}</div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {room?.name || b.room_id} · {start.toLocaleString()} – {end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => void handleCancel(b.id)}
                          disabled={busy !== "idle"}
                          className="text-xs px-3 py-1.5 rounded-md border border-border bg-card hover:bg-secondary transition-colors disabled:opacity-50"
                        >
                          {busy === "cancelling" ? "Cancelling…" : "Cancel"}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
