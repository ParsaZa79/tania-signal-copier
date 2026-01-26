"use client";

import { motion, useReducedMotion } from "framer-motion";
import { staggerContainer } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function PageContainer({ children, className }: PageContainerProps) {
  const prefersReducedMotion = useReducedMotion();

  if (prefersReducedMotion) {
    return <div className={cn("space-y-6", className)}>{children}</div>;
  }

  return (
    <motion.div
      className={cn("space-y-6", className)}
      variants={staggerContainer}
      initial="initial"
      animate="animate"
    >
      {children}
    </motion.div>
  );
}
