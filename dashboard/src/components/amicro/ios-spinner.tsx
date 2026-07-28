"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface IOSSpinnerProps {
  /** Rendered square size in px. Ticks scale with it. */
  size?: number;
  className?: string;
}

/**
 * Ticks use `bg-current` so the spinner inherits the colour of whatever button
 * it sits in, which varies between accent, outline and ghost variants.
 */
export const IOSSpinner = ({ size = 32, className }: IOSSpinnerProps) => (
  <span
      className={cn("loader-surface relative inline-block shrink-0", className)}
    style={{ width: size, height: size }}
    aria-hidden="true"
  >
    {Array.from({ length: 12 }).map((_, i) => (
      <span
        key={i}
        className="absolute inset-0 block"
        style={{ transform: `rotate(${i * 30}deg)` }}
      >
        <motion.span
          className="mx-auto block rounded-full bg-current"
          style={{ width: size / 16, height: size * 0.22 }}
          animate={{ opacity: [1, 0.2] }}
          transition={{
            duration: 1,
            repeat: Infinity,
            delay: i * (1 / 12),
            ease: "linear",
          }}
        />
      </span>
    ))}
  </span>
);
