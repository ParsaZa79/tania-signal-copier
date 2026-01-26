// Animation presets for Framer Motion
// Aligned with existing 200-300ms CSS transition patterns

export const pageTransition = {
  type: "tween" as const,
  ease: [0.4, 0, 0.2, 1] as [number, number, number, number], // Standard ease-out
  duration: 0.25, // 250ms
};

// Page-level fade animation
export const pageVariants = {
  initial: {
    opacity: 0,
  },
  animate: {
    opacity: 1,
  },
  exit: {
    opacity: 0,
  },
};

// Stagger container for child animations
export const staggerContainer = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.05, // 50ms between children
      delayChildren: 0.1,
    },
  },
};

// Individual stagger item animation
export const staggerItem = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: {
      type: "tween" as const,
      ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
      duration: 0.3,
    },
  },
};
