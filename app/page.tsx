"use client";

import { memo, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";
import {
  Broadcast,
  ChatCircleText,
  FileText,
  HeartStraight,
  MapTrifold,
  PhoneCall,
  ShieldCheck,
  ArrowLeft,
} from "@phosphor-icons/react";
import Logo from "@/components/Logo";

/* ------------------------------------------------------------------ */
/* Live ops preview — the product is its own hero asset.               */
/* ------------------------------------------------------------------ */
const PREVIEW_ROWS = [
  { name: "רחל אזולאי", status: "OK", label: "בסדר", c: "#4da8ff", sum: "בטוחה בבית, הכל תקין" },
  { name: "יוסי מרציאנו", status: "PENDING", label: "מתקשר", c: "#5b9eff", sum: "" },
  { name: "אבי שטרית", status: "NEEDS_HELP", label: "זקוק לעזרה", c: "#60c4ff", sum: "מבקש מים ותרופות, רחוב הגפן 12" },
  { name: "מרים דהן", status: "OK", label: "בסדר", c: "#4da8ff", sum: "במרחב מוגן עם הנכדים" },
];

const LivePreview = memo(function LivePreview() {
  const reduce = useReducedMotion();
  const [active, setActive] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => setActive((a) => (a + 1) % PREVIEW_ROWS.length), 2600);
    return () => clearInterval(iv);
  }, []);
  return (
    <div className="fade-up d3 relative">
      <motion.div
        animate={reduce ? {} : { y: [0, -6, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="lift overflow-hidden rounded-2xl border border-line bg-panel"
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <div className="flex items-center gap-2">
            <span className="pulse-ring h-2 w-2 rounded-full bg-pulse" />
            <span className="text-sm font-semibold">מבצע פעיל · בדיקת שלום</span>
          </div>
          <span className="font-mono2 text-[10px] tracking-[0.2em] text-faint" dir="ltr">LIVE</span>
        </div>
        <div className="grid grid-cols-3 divide-x divide-x-reverse divide-line border-b border-line py-4 text-center">
          {[
            { n: "183", l: "בסדר", c: "#4da8ff" },
            { n: "12", l: "זקוקים לעזרה", c: "#60c4ff" },
            { n: "2", l: "מצוקה", c: "#7db8e8" },
          ].map((s) => (
            <div key={s.l}>
              <div className="font-mono2 text-3xl font-semibold" style={{ color: s.c }}>{s.n}</div>
              <div className="mt-1 text-[11px] text-mut">{s.l}</div>
            </div>
          ))}
        </div>
        <ul className="divide-y divide-line px-2">
          {PREVIEW_ROWS.map((r, i) => (
            <li
              key={r.name}
              className="flex items-center gap-3 px-3 py-3 transition-colors duration-500"
              style={{ background: i === active ? "rgba(52,208,125,0.05)" : "transparent" }}
            >
              <span
                className={`h-2.5 w-2.5 flex-none rounded-full ${r.status === "PENDING" ? "pulse-ring" : ""}`}
                style={{ background: r.c }}
              />
              <div className="min-w-0 flex-1 text-start">
                <div className="text-[13.5px] font-medium">{r.name}</div>
                <div className="truncate text-[11.5px] text-faint">
                  {r.sum || <span className="ell text-blue">בשיחה</span>}
                </div>
              </div>
              <span
                className="rounded-md px-2.5 py-0.5 font-mono2 text-[10px] font-semibold text-ink"
                style={{ background: r.c }}
              >
                {r.label}
              </span>
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  );
});

/* ------------------------------------------------------------------ */

const BENTO = [
  {
    icon: Broadcast,
    title: "שיחות מקבילות, בלי תקרה",
    body: "אירוע עם אלף תושבים הוא לא אלף שעות של שיחות. כולם מקבלים שיחה בו-זמנית, בעברית, בטון אנושי ורגוע.",
    big: true,
  },
  {
    icon: HeartStraight,
    title: "תמיכה רגשית תוך כדי איסוף",
    body: "שאלה אחת בכל פעם, הקשבה אמיתית. והמידע החיוני נאסף בדרך.",
  },
  {
    icon: ShieldCheck,
    title: "טריאז' אוטומטי",
    body: "כל שיחה מסתיימת בסטטוס. מצוקה מסלימה מיד לאיש קשר ולמוקדן אנושי.",
  },
  {
    icon: ChatCircleText,
    title: "לא ענית? לא נעלמת",
    body: "SMS מיידי, שתי דקות המתנה, ושיחה נוספת. אפשר גם פשוט להשיב להודעה.",
  },
  {
    icon: MapTrifold,
    title: "מפה חיה למוקדן",
    body: "כל תושב הוא נקודה שמחליפה צבע בזמן אמת. וזזה לכתובת שנמסרה בשיחה.",
  },
  {
    icon: FileText,
    title: "תמלול מלא, שמור",
    body: "כל שיחה וכל SMS נשמרים. סיכום למבט מהיר, תמליל מלא כשצריך להעמיק.",
  },
];

const MARQUEE = ["מתקשרים לכולם", "בסדר", "זקוק לעזרה", "מצוקה — אדם אמיתי", "לא נענה — שיחה חוזרת", "תמלול מלא", "מפה חיה"];

function ScrubLine({ text, range, progress, n }: {
  text: string;
  range: [number, number];
  progress: ReturnType<typeof useScroll>["scrollYProgress"];
  n: string;
}) {
  const opacity = useTransform(progress, range, [0.2, 1]);
  const y = useTransform(progress, range, [22, 0]);
  return (
    <motion.div style={{ opacity, y }} className="flex items-start gap-5 sm:gap-8">
      <span className="font-mono2 mt-2 text-base text-pulse sm:text-lg" dir="ltr">{n}</span>
      <p className="font-display text-3xl font-extrabold leading-[1.3] tracking-tight sm:text-5xl">
        {text}
      </p>
    </motion.div>
  );
}

export default function Landing() {
  const scrubRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: scrubRef,
    offset: ["start 0.85", "end 0.45"],
  });

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")),
      { threshold: 0.15 }
    );
    document.querySelectorAll(".reveal").forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  return (
    <main className="grain w-full max-w-full overflow-x-hidden bg-ink text-fg">
      {/* floating pill nav */}
      <div className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
        <nav className="glass flex w-full max-w-3xl items-center justify-between rounded-full bg-ink/70 py-2 pe-2 ps-5">
          <Link href="/" className="flex items-center gap-2.5">
            <Logo className="h-6 w-6 text-pulse" />
            <span className="font-display text-xl font-black tracking-tight">בסדר</span>
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 rounded-full bg-pulse px-4 py-2 text-sm font-bold text-ink transition-transform hover:scale-[1.03] active:scale-[0.98]"
          >
            למוקד החי
            <ArrowLeft size={15} weight="bold" />
          </Link>
        </nav>
      </div>

      {/* ---------- attention: editorial asymmetric hero ---------- */}
      <section className="relative mx-auto max-w-7xl px-5 pb-24 pt-36 sm:pt-44">
        <div className="grid items-center gap-14 lg:grid-cols-12 lg:gap-8">
          {/* text — right side in RTL, the wider column */}
          <div className="lg:col-span-7">
            <div className="fade-up flex items-center gap-3">
              <span className="pulse-ring h-2 w-2 rounded-full bg-pulse" />
              <span className="text-[13px] font-medium tracking-wide text-mut">
                מערך תגובה קולי לאחר אירועי חירום
              </span>
            </div>

            <h1 className="fade-up d1 mt-7 font-display text-[clamp(2.9rem,5.6vw,5rem)] font-black leading-[1.04] tracking-tight">
              <span className="block text-fg">כשמשהו קורה —</span>
              <span className="block text-mut">מתקשרים לכולם.</span>
              <span className="block text-pulse">ושומעים שהכל בסדר.</span>
            </h1>

            <p className="fade-up d2 mt-8 max-w-xl text-base leading-relaxed text-mut sm:text-lg">
              אחרי אזעקה, רעידת אדמה או כל אירוע — "בסדר" מתקשר לכל תושב בו-זמנית,
              שואל בעדינות מה שלומו, ומציף למוקדן רק את מי שבאמת צריך עזרה.
              בדקות, לא בשעות.
            </p>

            <div className="fade-up d2 mt-9 flex flex-wrap items-center gap-3">
              <Link
                href="/dashboard"
                className="lift flex items-center gap-2 rounded-xl bg-pulse px-7 py-4 text-base font-bold text-ink transition-transform hover:-translate-y-[1px] active:translate-y-0"
              >
                <PhoneCall size={19} weight="fill" />
                פתחו את המוקד החי
              </Link>
              <a
                href="#how"
                className="edge rounded-xl bg-white/[0.02] px-7 py-4 text-base font-semibold text-mut transition-colors hover:text-fg"
              >
                איך זה עובד
              </a>
            </div>
          </div>

          {/* asset — left side, offset down for asymmetric whitespace */}
          <div className="lg:col-span-5 lg:mt-20">
            <LivePreview />
          </div>
        </div>
      </section>

      {/* kinetic marquee */}
      <div className="relative overflow-hidden border-y border-line bg-ink2 py-5" dir="ltr">
        <div className="flex w-max marquee-track" aria-hidden>
          {[0, 1].map((copy) => (
            <div key={copy} className="flex items-center">
              {MARQUEE.map((w) => (
                <span key={`${copy}-${w}`} className="flex items-center" dir="rtl">
                  <span className="whitespace-nowrap px-7 font-display text-xl font-black tracking-tight text-mut">
                    {w}
                  </span>
                  <Logo className="h-4 w-4 flex-none text-pulse/50" />
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ---------- interest: gapless bento ---------- */}
      <section className="mx-auto max-w-7xl px-5 py-32 md:py-44">
        <div className="flex items-baseline gap-5">
          <span className="font-mono2 text-sm text-pulse" dir="ltr">01</span>
          <h2 className="reveal font-display text-3xl font-black tracking-tight sm:text-[2.8rem] sm:leading-[1.15]">
            בנוי לרגעים שבהם
            <span className="text-mut"> כל דקה חשובה.</span>
          </h2>
        </div>

        <div className="mt-14 grid grid-flow-dense gap-4 md:grid-cols-3">
          {BENTO.map((f, i) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                style={{ transitionDelay: `${(i % 3) * 70}ms` }}
                className={`reveal edge group relative overflow-hidden rounded-2xl bg-gradient-to-b from-white/[0.025] to-transparent p-8 transition-colors duration-300 hover:border-white/15 ${
                  f.big ? "md:col-span-2 md:row-span-2 md:p-10" : ""
                }`}
              >
                <div className="inline-flex rounded-xl border border-line bg-white/[0.03] p-3">
                  <Icon size={f.big ? 28 : 22} weight="duotone" className="text-pulse" />
                </div>
                <h3 className={`mt-6 font-display font-extrabold ${f.big ? "text-2xl" : "text-lg"}`}>
                  {f.title}
                </h3>
                <p className={`mt-2.5 leading-relaxed text-mut ${f.big ? "max-w-[48ch] text-base" : "text-sm"}`}>
                  {f.body}
                </p>
                {f.big && (
                  <div className="mt-10 grid grid-cols-12 gap-2.5" aria-hidden>
                    {Array.from({ length: 36 }).map((_, d) => (
                      <span
                        key={d}
                        className="bdot aspect-square rounded-full"
                        style={{
                          background: d % 9 === 4 ? "#60c4ff" : d % 13 === 7 ? "#5b9eff" : "#4da8ff",
                          transitionDelay: `${300 + d * 28}ms`,
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ---------- desire: scroll-scrubbed steps ---------- */}
      <section id="how" ref={scrubRef} className="border-y border-line bg-ink2">
        <div className="mx-auto flex max-w-5xl flex-col gap-16 px-5 py-32 md:py-48">
          <ScrubLine n="01" progress={scrollYProgress} range={[0, 0.33]} text="מזינים רשימת טלפונים ובוחרים תרחיש." />
          <ScrubLine n="02" progress={scrollYProgress} range={[0.28, 0.62]} text='לחיצה אחת, ו"בסדר" מתקשר לכולם בו-זמנית.' />
          <ScrubLine n="03" progress={scrollYProgress} range={[0.56, 0.92]} text="המפה מתמלאת בכחול, והמוקדן רואה רק את מי שצריך אותו." />
        </div>
      </section>

      {/* trust — editorial, divided, not boxed */}
      <section className="mx-auto max-w-7xl px-5 py-28 md:py-36">
        <div className="grid gap-10 md:grid-cols-3 md:gap-0 md:divide-x md:divide-x-reverse md:divide-line">
          {[
            { t: "רק בהסכמה", b: "מתקשרים אך ורק למי שאישר מראש לקבל שיחות בחירום." },
            { t: "מחבר, לא מטפל", b: "הסוכן בודק שלום ומחבר לאדם אנושי. לעולם לא מאבחן ולא נותן ייעוץ רפואי." },
            { t: "ספק? מחמירים", b: "כשלא ברור, המערכת מסמנת לחומרה. אדום לעולם לא נסגר אוטומטית." },
          ].map((x, i) => (
            <div key={x.t} style={{ transitionDelay: `${i * 80}ms` }} className="reveal md:px-8">
              <div className="font-display text-xl font-extrabold text-pulse">{x.t}</div>
              <p className="mt-2.5 text-sm leading-relaxed text-mut">{x.b}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- action ---------- */}
      <section className="border-t border-line">
        <div className="mx-auto max-w-7xl px-5 py-32 text-center md:py-44">
          <h2 className="reveal mx-auto max-w-4xl font-display text-4xl font-black leading-tight tracking-tight sm:text-6xl">
            מוכנים לשמוע <span className="text-pulse">שהכל בסדר?</span>
          </h2>
          <div className="reveal" style={{ transitionDelay: "100ms" }}>
            <Link
              href="/dashboard"
              className="lift mt-10 inline-flex items-center gap-2.5 rounded-xl bg-pulse px-9 py-4.5 text-lg font-bold text-ink transition-transform hover:-translate-y-[1px]"
            >
              <PhoneCall size={21} weight="fill" />
              למוקד החי
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-7 text-xs text-faint">
          <div className="flex items-center gap-2">
            <Logo className="h-4 w-4 text-pulse" />
            <span className="font-display font-extrabold">בסדר · Beseder</span>
          </div>
          <span>נבנה בהאקתון Dial — My Agent Has a Phone, תל אביב 2026</span>
        </div>
      </footer>
    </main>
  );
}
