"use client";

import dynamic from "next/dynamic";

const Console = dynamic(() => import("@/components/Console"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen items-center justify-center bg-ink text-mut">
      טוען את המוקד החי…
    </div>
  ),
});

export default function DashboardPage() {
  return <Console />;
}
