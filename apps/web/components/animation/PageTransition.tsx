// apps/web/components/animation/PageTransition.tsx
"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { usePathname } from "next/navigation";
import React, { useEffect } from "react";

// ---- Tuning knobs (feel free to tweak) ----
const EASE = [0.25, 0.8, 0.25, 1] as const; // gentle, premium curve
const OPACITY_DUR = 0; // slower fade
const BLUR_DUR = 0; // subtle blur in sync with fade
const ENTER_Y = 0; // px slide in
const EXIT_Y = 0;
// -------------------------------------------

export default function PageTransition({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const prefersReduced = useReducedMotion();

  // Reset the scroll of the main content area on each route change
  useEffect(() => {
    const main = document.querySelector("main");
    if (main) (main as HTMLElement).scrollTop = 0;
  }, [pathname]);

  // Springy movement for position/scale (smoother than tweens)
  const spring = prefersReduced
    ? { duration: 0.58, ease: EASE }
    : { type: "spring", stiffness: 95, damping: 28, mass: 1.0 };

  return (
    <div className="relative">
      {/* 'sync' mounts next immediately -> no blank gap */}
      <AnimatePresence mode="sync" initial={false}>
        <motion.div
          key={pathname}
          initial={{
            opacity: 0,
            y: ENTER_Y,
            scale: 0.985,
            filter: "blur(2px)",
          }}
          animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
          // Exit is taken out of flow so it doesn't push the new page down
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
            opacity: { duration: OPACITY_DUR, ease: EASE },
            filter: { duration: BLUR_DUR, ease: EASE },
            y: spring,
            scale: spring,
          }}
          style={{ willChange: "transform, opacity, filter" }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
