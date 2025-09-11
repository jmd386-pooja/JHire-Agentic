// apps/web/components/animation/AnimatedInView.tsx
"use client";

import { motion, useInView, useReducedMotion } from "framer-motion";
import React, { useRef, PropsWithChildren } from "react";
import clsx from "clsx";

// Slower, smoother defaults everywhere this wrapper is used.
type Props = PropsWithChildren<{
  as?: keyof JSX.IntrinsicElements;
  className?: string;
  amount?: number; // 0..1 portion of element that must be visible
  offsetY?: number; // px translate on enter/exit
  duration?: number; // seconds
  delay?: number; // seconds
}>;

export function AnimatedInView({
  as: Tag = "div",
  className,
  children,
  amount = 0.25,
  offsetY = 14,
  duration = 0.65,
  delay = 0,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const inView = useInView(ref, { amount, margin: "0px 0px -10% 0px" });
  const prefersReduced = useReducedMotion();

  const transition = prefersReduced
    ? { duration: Math.min(0.4, duration) }
    : { duration, delay, ease: [0.25, 0.8, 0.25, 1] };

  return (
    <motion.div
      ref={ref}
      className={clsx(className)}
      initial={{ opacity: 0, y: offsetY }}
      animate={
        inView
          ? { opacity: 1, y: 0, pointerEvents: "auto" }
          : { opacity: 0, y: offsetY, pointerEvents: "none" }
      }
      transition={transition}
      style={{ willChange: "transform, opacity" }}
    >
      {children}
    </motion.div>
  );
}
