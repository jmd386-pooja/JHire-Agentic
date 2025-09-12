"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { usePathname } from "next/navigation";
import React, { useEffect } from "react";

// ---- Tuning knobs ----
const EASE = [0.25, 0.8, 0.25, 1] as const;
const OPACITY_DUR = 0; // keep fade instant per your current settings
const BLUR_DUR = 0;
const ENTER_Y = 0;
const EXIT_Y = 0;
// -----------------------

export default function PageTransition({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const prefersReduced = useReducedMotion();

  // Reset scroll on route change (handles both body and inner scroll containers)
  useEffect(() => {
    const candidates: (HTMLElement | null | undefined)[] = [
      // inner scroll wrapper if you've marked it
      document.querySelector<HTMLElement>("[data-scroll-root='true']"),
      // main element (older layouts)
      document.querySelector<HTMLElement>("main"),
      // fallbacks
      document.scrollingElement as HTMLElement,
      document.documentElement,
      document.body as unknown as HTMLElement,
    ];

    for (const el of candidates) {
      if (el && typeof el.scrollTop === "number") {
        try {
          el.scrollTop = 0;
        } catch {}
      }
    }
  }, [pathname]);

  const spring = prefersReduced
    ? { duration: 0.58, ease: EASE as any }
    : { type: "spring", stiffness: 95, damping: 28, mass: 1.0 };

  return (
    <div className="relative w-full min-w-0 max-w-full overflow-x-hidden">
      <AnimatePresence mode="sync" initial={false}>
        <motion.div
          key={pathname}
          className="w-full min-w-0 max-w-full overflow-x-hidden"
          initial={{
            opacity: 0,
            y: ENTER_Y,
            scale: 0.985,
            filter: "blur(2px)",
          }}
          animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
          exit={{
            opacity: 0,
            y: EXIT_Y,
            scale: 0.992,
            filter: "blur(1px)",
            position: "absolute",
            inset: 0,
            width: "100%",
          }}
          transition={{
            opacity: { duration: OPACITY_DUR, ease: EASE as any },
            filter: { duration: BLUR_DUR, ease: EASE as any },
            y: spring as any,
            scale: spring as any,
          }}
          style={{ willChange: "transform, opacity, filter" }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
