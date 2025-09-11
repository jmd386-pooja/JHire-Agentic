import Sidebar from "@/components/layout/sidebar";
import PageTransition from "@/components/animation/PageTransition";
import { Suspense } from "react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar />
      <main className="relative flex-1 min-w-0 overflow-y-auto bg-gradient-to-b from-slate-50 to-zinc-100">
        <Suspense
          fallback={
            <div className="p-6">
              <div className="h-6 w-40 rounded bg-gray-200 mb-4" />
              <div className="h-24 w-full rounded bg-gray-200" />
            </div>
          }
        >
          <PageTransition>{children}</PageTransition>
        </Suspense>
      </main>
    </div>
  );
}
