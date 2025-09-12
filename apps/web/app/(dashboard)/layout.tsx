import Sidebar from "@/components/layout/sidebar";
import PageTransition from "@/components/animation/PageTransition";
import { Suspense } from "react";
import Image from "next/image";
import JmanLogo from "@/images/JMANLogoBlue.png";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh overflow-hidden">

      {/* main column; never allow x-overflow */}
      <main className="flex flex-1 min-w-0 flex-col overflow-x-hidden bg-gradient-to-b from-slate-50 to-zinc-100">
        {/* only this area scrolls */}
        <Sidebar />
        <div className="flex-1 min-h-0 overflow-y-auto">
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
        </div>

        <footer className="mt-auto shrink-0 w-full bg-gray-200 py-2 px-2">
          <div className="max-w-7xl mx-auto flex justify-between items-center">
            <p className="text-sm text-gray-600 m-0">
              © 2024 JMAN, All Rights Reserved
            </p>
            <Image
              src={JmanLogo}
              alt="JMAN Logo"
              width={120}
              height={40}
              className="m-0"
            />
          </div>
        </footer>
      </main>
    </div>
  );
}
