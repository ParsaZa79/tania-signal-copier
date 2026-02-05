"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "framer-motion";
import { staggerItem } from "@/lib/motion";

type AnimatedSectionProps = HTMLMotionProps<"div"> & {
  children: React.ReactNode;
  className?: string;
};

export function AnimatedSection({
  children,
  className,
  ...props
}: AnimatedSectionProps) {
  const prefersReducedMotion = useReducedMotion();

  if (prefersReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      variants={staggerItem}
      initial="initial"
      animate="animate"
      {...props}
    >
      {children}
    </motion.div>
  );
}
