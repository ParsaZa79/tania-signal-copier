"use client";

import { motion } from "framer-motion";

export const SquareSnake = () => {
  return (
    <div className="grid h-10 w-10 grid-cols-3 gap-1" aria-hidden="true">
      {[
        [0, 0],
        [1, 0],
        [2, 0],
        [0, 1],
        [1, 1],
        [2, 1],
        [0, 2],
        [1, 2],
        [2, 2],
      ].map(([x, y], i) => (
        <motion.div
          key={i}
          className="h-full w-full rounded-sm bg-zinc-800 dark:bg-white"
          initial={{ opacity: 0.1 }}
          animate={{ opacity: [0.1, 1, 0.1] }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            delay: (x + y) * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
};
