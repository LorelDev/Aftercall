"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import L from "leaflet";
import {
  CircleNotch,
  ClipboardText,
  PhoneCall,
  Plus,
  Siren,
  X,
} from "@phosphor-icons/react";
import Logo from "@/components/Logo";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const COLORS: Record<string, string> = {
  OK: "#2dd576",
  NEEDS_HELP: "#f5b324",
  DISTRESS: "#ff4d5e",
  UNREACHED: "#6b7a94",
  PENDING: "#4d8dff",
};
const LABELS: Record<string, string> = {
  OK: "בסדר",
  NEEDS_HELP: "זקוק/ה לעזרה",
  DISTRESS: "מצוקה",
  UNREACHED: "לא נענה",
  PENDING: "מתקשר…",
  total: 'סה"כ',
};

type PendingPerson = { id: number; phone: string; name: string; lat: number; lng: number };
type Person = {
  person_id: number;
  name: string;
  phone?: string;
  lat: number;
  lng: number;
  status: string;
  attempt?: number;
  summary?: string;
  transcript?: string;
  updated_at?: number | null;
};
type StatusData = {
  counters?: Record<string, number>;
  people?: Person[];
  alerts?: { name: string; message: string }[];
};
type Health = { dial_dry_run: boolean; supabase: boolean } | null;

function dotIcon(status: string) {
  const c = COLORS[status] || COLORS.PENDING;
  return L.divIcon({
    className: "",
    html: `<span class="mdot ${status}" style="background:${c};box-shadow:0 0 10px ${c}"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

function Transcript({ p, open, onToggle }: { p: Person; open: boolean; onToggle: () => void }) {
  const t = (p.transcript || "")
    .split("\n")
    .filter((l) => !/STATUS\s*=/.test(l))
    .join("\n")
    .trim();
  if (!t) return null;
  const lines = t.split("\n").map((s) => s.trim()).filter(Boolean);
  return (
    <div className="mt-2.5 border-t border-dashed border-line pt-2">
      <button
        onClick={onToggle}
        className="flex items-center gap-1.5 text-[11px] font-semibold text-blue transition hover:brightness-125"
      >
        <span className={`text-[9px] transition-transform ${open ? "rotate-90" : ""}`}>◀</span>
        תמליל מלא
      </button>
      {open && (
        <div className="mt-2.5 flex max-h-64 flex-col gap-1.5 overflow-auto pe-1">
          {lines.map((ln, i) => {
            const m = ln.match(/^(User|Agent)\s*:\s*(.*)$/i);
            if (!m)
              return (
                <div key={i} className="whitespace-pre-wrap rounded-lg border border-line bg-ink2 px-2.5 py-1.5 text-xs leading-relaxed">
                  {ln}
                </div>
              );
            const agent = m[1].toLowerCase() === "agent";
            return (
              <div
                key={i}
                className={`max-w-[92%] rounded-xl px-2.5 py-1.5 text-xs leading-relaxed ${
                  agent
                    ? "self-start rounded-ss-sm border border-blue/25 bg-blue/10"
                    : "self-end rounded-se-sm border border-pulse/20 bg-pulse/10"
                }`}
              >
                <span className="mb-0.5 block text-[9.5px] font-bold tracking-widest text-faint">
                  {agent ? "הסוכן" : "התושב/ת"}
                </span>
                {m[2]}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Console() {
  const mapRef = useRef<L.Map | null>(null);
  const mapElRef = useRef<HTMLDivElement>(null);
  const pendingMarkers = useRef<Map<number, L.Marker>>(new Map());
  const liveMarkers = useRef<Map<number, L.Marker>>(new Map());
  const nextId = useRef(1);

  const [pending, setPending] = useState<PendingPerson[]>([]);
  const [eventId, setEventId] = useState<number | null>(null);
  const [data, setData] = useState<StatusData>({});
  const [health, setHealth] = useState<Health>(null);
  const [serverUp, setServerUp] = useState(false);
  const [playbooks, setPlaybooks] = useState<string[]>(["wellbeing_check"]);
  const [playbook, setPlaybook] = useState("wellbeing_check");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [firing, setFiring] = useState(false);
  const [fireMsg, setFireMsg] = useState("");
  const [openT, setOpenT] = useState<Set<number>>(new Set());
  const [updatedAt, setUpdatedAt] = useState("");

  // map init
  useEffect(() => {
    if (!mapElRef.current || mapRef.current) return;
    const map = L.map(mapElRef.current, { zoomControl: false }).setView([32.07, 34.78], 15);
    L.control.zoom({ position: "bottomleft" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(mapElRef.current);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // health + playbooks
  useEffect(() => {
    const check = async () => {
      try {
        const h = await (await fetch(`${API}/health`)).json();
        setHealth(h);
        setServerUp(true);
      } catch {
        setServerUp(false);
      }
    };
    const load = async () => {
      try {
        const j = await (await fetch(`${API}/playbooks`)).json();
        const order = (p: string) => (p === "wellbeing_check" ? 0 : 1);
        setPlaybooks([...j.playbooks].sort((a: string, b: string) => order(a) - order(b)));
      } catch {}
    };
    check();
    load();
    const iv = setInterval(check, 5000);
    return () => clearInterval(iv);
  }, []);

  // status polling
  useEffect(() => {
    if (!eventId) return;
    const poll = async () => {
      try {
        const d = await (await fetch(`${API}/events/${eventId}/status`)).json();
        setData(d);
        setUpdatedAt(new Date().toLocaleTimeString("he-IL"));
      } catch {}
    };
    poll();
    const iv = setInterval(poll, 2000);
    return () => clearInterval(iv);
  }, [eventId]);

  // live markers sync
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    (data.people || []).forEach((p) => {
      let m = liveMarkers.current.get(p.person_id);
      if (!m) {
        m = L.marker([p.lat, p.lng], { icon: dotIcon(p.status) }).addTo(map);
        liveMarkers.current.set(p.person_id, m);
      }
      m.setIcon(dotIcon(p.status));
      m.setLatLng([p.lat, p.lng]); // the person may have told the agent where they are
      m.bindPopup(
        `<b>${p.name}</b> <span style="background:${COLORS[p.status]};color:#0b0f17;border-radius:20px;padding:2px 8px;font-size:10px;font-weight:700">${LABELS[p.status] || p.status}</span><br><small>${p.summary || "…"}</small>`
      );
    });
  }, [data]);

  const addPhone = useCallback(() => {
    const map = mapRef.current;
    let ph = phone.trim();
    if (!ph || !map) return;
    if (!ph.startsWith("+")) ph = "+" + ph.replace(/[^0-9]/g, "");
    const c = map.getCenter();
    const lat = c.lat + (Math.random() - 0.5) * 0.006;
    const lng = c.lng + (Math.random() - 0.5) * 0.006;
    const id = nextId.current++;
    const entry: PendingPerson = { id, phone: ph, name: name.trim(), lat, lng };
    const marker = L.marker([lat, lng], { icon: dotIcon("PENDING"), draggable: true }).addTo(map);
    marker.bindPopup(`<b>${entry.name || ph}</b><br><small>גרור למיקום מדויק</small>`);
    marker.on("dragend", () => {
      const ll = marker.getLatLng();
      setPending((prev) => prev.map((p) => (p.id === id ? { ...p, lat: ll.lat, lng: ll.lng } : p)));
    });
    pendingMarkers.current.set(id, marker);
    setPending((prev) => [...prev, entry]);
    setPhone("");
    setName("");
  }, [phone, name]);

  const removePhone = (id: number) => {
    pendingMarkers.current.get(id)?.remove();
    pendingMarkers.current.delete(id);
    setPending((prev) => prev.filter((p) => p.id !== id));
  };

  const fire = async () => {
    if (!pending.length || firing) return;
    setFiring(true);
    setFireMsg("");
    try {
      const r = await fetch(`${API}/campaigns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playbook,
          people: pending.map((p) => ({ name: p.name, phone: p.phone, lat: p.lat, lng: p.lng })),
        }),
      });
      const j = await r.json();
      setEventId(j.event_id);
      (j.people || []).forEach((p: { person_id: number }, i: number) => {
        const src = pending[i];
        const m = src && pendingMarkers.current.get(src.id);
        if (m) liveMarkers.current.set(p.person_id, m);
      });
      pendingMarkers.current.clear();
      setPending([]);
      setFireMsg(
        j.dry_run
          ? "מצב הדגמה — אין מפתח Dial, השיחות מדומות."
          : `${j.targets} שיחות חיות יצאו במקביל. המידע יתעדכן כאן.`
      );
    } catch {
      setFireMsg("שגיאה בשליחה — ודאו שהשרת רץ על :8000.");
    } finally {
      setFiring(false);
    }
  };

  const toggleT = (pid: number) =>
    setOpenT((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid);
      else next.add(pid);
      return next;
    });

  const counters = data.counters || {};
  const people = data.people || [];
  const alerts = data.alerts || [];
  const counterOrder = ["OK", "NEEDS_HELP", "DISTRESS", "UNREACHED", "PENDING", "total"];

  return (
    <div className="flex h-dvh flex-col bg-ink text-fg lg:grid lg:grid-cols-[400px_1fr_380px]">
      {/* ---- controls ---- */}
      <div className="order-1 overflow-y-auto border-b border-line bg-gradient-to-b from-panel to-ink2 p-5 lg:border-b-0 lg:border-e">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 transition hover:opacity-80">
            <Logo className="h-8 w-8 text-pulse" />
            <span className="text-2xl font-extrabold tracking-tight">בסדר</span>
            <span className="pb-0.5 pt-2 font-mono2 text-[9.5px] font-semibold tracking-[0.22em] text-faint">
              LIVE OPS
            </span>
          </Link>
        </div>
        <div className="mt-1.5 text-xs leading-relaxed text-mut">
          מוקד חי — שיחות AI מקבילות, איסוף מידע ומיפוי בזמן אמת
        </div>

        <div
          className={`mt-4 flex items-center gap-2 rounded-xl border px-3 py-2.5 text-xs ${
            serverUp ? "border-pulse/35 bg-inset" : "border-line bg-inset"
          }`}
        >
          <span
            className={`h-2 w-2 flex-none rounded-full ${
              serverUp ? "bg-pulse shadow-[0_0_8px_rgba(45,213,118,0.8)]" : "bg-faint"
            }`}
          />
          <span className="text-mut">
            {serverUp ? (
              health?.dial_dry_run ? (
                <>מחובר · <b className="text-fg">מצב הדגמה</b> (שיחות מדומות)</>
              ) : (
                <>
                  מחובר · <b className="text-fg">שיחות אמת פעילות</b>
                  {health?.supabase ? " · תמלילים נשמרים" : ""}
                </>
              )
            ) : (
              <>אין חיבור לשרת — הפעילו את ה-backend על פורט 8000</>
            )}
          </span>
        </div>

        <label className="mb-1.5 mt-4 block text-[11px] font-semibold tracking-widest text-faint">
          תרחיש (PLAYBOOK)
        </label>
        <select
          value={playbook}
          onChange={(e) => setPlaybook(e.target.value)}
          className="w-full rounded-xl border border-line bg-inset px-3 py-2.5 text-sm outline-none transition focus:border-blue"
        >
          {playbooks.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <label className="mb-1.5 mt-4 block text-[11px] font-semibold tracking-widest text-faint">
          הוספת מספרי טלפון
        </label>
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addPhone()}
            placeholder="+972552285564"
            inputMode="tel"
            dir="ltr"
            className="w-full rounded-xl border border-line bg-inset px-3 py-2.5 text-right font-mono2 text-sm outline-none transition placeholder:text-faint focus:border-blue"
          />
          <button
            onClick={addPhone}
            className="flex cursor-pointer items-center gap-1.5 rounded-xl border border-line bg-inset px-4 text-sm font-semibold transition hover:border-line2 active:scale-[0.97]"
          >
            <Plus size={15} weight="bold" />
            הוסף
          </button>
        </div>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addPhone()}
          placeholder="שם (אופציונלי)"
          className="mt-2 w-full rounded-xl border border-line bg-inset px-3 py-2.5 text-sm outline-none transition placeholder:text-faint focus:border-blue"
        />
        <div className="mt-1.5 text-[11px] leading-relaxed text-faint">
          Enter מוסיף מספר. כל מספר הוא נקודה על המפה — גררו אותה למיקום מדויק.
        </div>

        {pending.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {pending.map((p) => (
              <span
                key={p.id}
                className="fade-up flex items-center gap-1.5 rounded-full border border-line2 bg-inset px-3 py-1 text-xs"
              >
                <span className="h-2 w-2 rounded-full bg-blue" />
                <b>{p.name || p.phone}</b>
                {p.name && (
                  <span dir="ltr" className="font-mono2 text-[10px] text-mut">
                    {p.phone}
                  </span>
                )}
                <button
                  onClick={() => removePhone(p.id)}
                  aria-label={`הסרת ${p.name || p.phone}`}
                  className="cursor-pointer p-1 text-faint transition hover:text-red"
                >
                  <X size={12} weight="bold" />
                </button>
              </span>
            ))}
          </div>
        )}

        <button
          onClick={fire}
          disabled={!pending.length || !serverUp || firing}
          className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-pulse py-3.5 text-base font-bold text-ink transition hover:-translate-y-[1px] hover:brightness-110 active:translate-y-0 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0"
        >
          {firing ? (
            <>
              <CircleNotch size={19} weight="bold" className="animate-spin" />
              מחייג…
            </>
          ) : (
            <>
              <PhoneCall size={19} weight="fill" />
              התקשר לכולם עכשיו
            </>
          )}
        </button>
        <div className="mt-1.5 text-[11px] text-faint">
          {fireMsg || (pending.length ? `${pending.length} מספרים מוכנים לחיוג מקבילי.` : "הוסיפו לפחות מספר אחד.")}
        </div>

        {/* counters */}
        <div className="mt-5 border-t border-line pt-4">
          <div className="mb-2.5 text-[11px] font-bold tracking-widest text-mut">
            מצב המבצע
          </div>
          {Object.keys(counters).length > 0 ? (
            <div className="grid grid-cols-3 overflow-hidden rounded-2xl border border-line bg-inset">
              {counterOrder
                .filter((k) => k in counters)
                .map((k) => (
                  <div key={k} className="border-b border-e border-line px-3 py-2.5 last:border-e-0">
                    <div
                      className="font-mono2 text-2xl font-semibold leading-none"
                      style={{ color: COLORS[k] || "var(--color-fg)" }}
                    >
                      {counters[k]}
                    </div>
                    <div className="mt-1 text-[10.5px] text-mut">{LABELS[k] || k}</div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-line px-4 py-5 text-center text-xs leading-relaxed text-faint">
              עוד אין מבצע פעיל.
              <br />
              הוסיפו מספרים והתקשרו — המספרים יופיעו כאן.
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-mut">
            {(["OK", "NEEDS_HELP", "DISTRESS", "UNREACHED", "PENDING"] as const).map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: COLORS[k] }} />
                {LABELS[k]}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ---- map ---- */}
      <div ref={mapElRef} className="order-2 h-[42dvh] min-h-[280px] lg:h-auto" />

      {/* ---- feed ---- */}
      <div className="order-3 flex-1 overflow-y-auto border-t border-line bg-gradient-to-b from-panel to-ink2 p-4 lg:border-s lg:border-t-0">
        <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-widest text-mut">
          <Siren size={14} weight="duotone" className="text-red" />
          התראות למוקדן אנושי
        </div>
        <div className="mt-2.5">
          {alerts.length ? (
            [...alerts].reverse().map((a, i) => (
              <div
                key={i}
                className="mb-2 rounded-xl border border-red/30 bg-red/5 px-3 py-2 text-xs leading-relaxed"
              >
                <b className="text-[#ffb3ba]">{a.name}</b> — {a.message}
              </div>
            ))
          ) : (
            <div className="text-xs text-faint">אין התראות.</div>
          )}
        </div>

        <div className="mt-5 border-t border-line pt-4">
          <div className="flex items-baseline justify-between">
            <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-widest text-mut">
              <ClipboardText size={14} weight="duotone" className="text-pulse" />
              מידע שנאסף בזמן אמת
            </div>
            {updatedAt && (
              <span dir="ltr" className="font-mono2 text-[10px] text-faint">
                עודכן {updatedAt}
              </span>
            )}
          </div>
          <div className="mt-2 divide-y divide-line">
            {people.length ? (
              people.map((p) => (
                <div
                  key={p.person_id}
                  className={`relative py-3 ps-3.5 transition-colors hover:bg-ink2/60 ${
                    p.status === "DISTRESS" ? "bg-red/5" : ""
                  }`}
                >
                  <span
                    aria-hidden
                    className="absolute inset-y-2 start-0 w-[3px] rounded-full"
                    style={{ background: COLORS[p.status] }}
                  />
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold">{p.name}</div>
                      {p.phone && (
                        <div dir="ltr" className="text-right font-mono2 text-[10px] text-faint">
                          {p.phone}
                        </div>
                      )}
                    </div>
                    <span
                      className="whitespace-nowrap rounded-full px-2.5 py-1 font-mono2 text-[10px] font-semibold text-ink"
                      style={{ background: COLORS[p.status] }}
                    >
                      {LABELS[p.status] || p.status}
                    </span>
                  </div>
                  {p.status === "PENDING" ? (
                    <div className="ell mt-1.5 text-[11.5px] text-blue">בשיחה / ממתין</div>
                  ) : (
                    <div className="mt-1.5 text-xs leading-relaxed text-mut">{p.summary || "—"}</div>
                  )}
                  {(p.attempt || 1) > 1 && (
                    <div className="mt-1 font-mono2 text-[10px] text-faint">ניסיון {p.attempt}</div>
                  )}
                  <Transcript p={p} open={openT.has(p.person_id)} onToggle={() => toggleT(p.person_id)} />
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-line px-4 py-6 text-center text-xs leading-relaxed text-faint">
                אין עדיין שיחות.
                <br />
                הוסיפו מספרים והתקשרו — המידע ייאסף כאן בזמן אמת.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
