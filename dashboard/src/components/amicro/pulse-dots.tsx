"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

export const PulseDots = ({ className }: { className?: string }) => {
  return (
    <div className={cn("flex space-x-1.5", className)} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="h-2.5 w-2.5 rounded-full bg-zinc-800 dark:bg-white"
          animate={{ opacity: [0.2, 1, 0.2] }}
          transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  );
};
