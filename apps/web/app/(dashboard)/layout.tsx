"use client";

import type React from "react";

import Sidebar from "@/components/layout/sidebar";
import PageTransition from "@/components/animation/PageTransition";
import { Suspense, useState, useEffect } from "react";
import Image from "next/image";
import JmanLogo from "@/images/JMANLogoBlue.png";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);

  // Listen for sidebar state changes
  useEffect(() => {
    const handleSidebarToggle = (event: CustomEvent) => {
      setSidebarExpanded(event.detail.expanded);
    };

    window.addEventListener(
      "sidebarToggle",
      handleSidebarToggle as EventListener
    );
    return () => {
      window.removeEventListener(
        "sidebarToggle",
        handleSidebarToggle as EventListener
      );
    };
  }, []);

  return (
    <div className="flex min-h-screen relative">
      {/* Fixed sidebar that stays in place */}
      <Sidebar onToggle={setSidebarExpanded} />

      {/* Content column with proper margin to account for fixed sidebar */}
      <main
        className={`flex flex-1 min-w-0 flex-col bg-gradient-to-b from-slate-50 to-zinc-100 transition-[margin-left] duration-300 ${
          sidebarExpanded ? "ml-64" : "ml-16"
        }`}
      >
        {/* Scrollable content area */}
        <div
          className="flex-1 min-h-screen overflow-y-auto"
          data-scroll-root="true"
        >
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

        <footer className="mt-auto shrink-0 w-full bg-gray-200 py-2 px-2 sticky bottom-0">
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
