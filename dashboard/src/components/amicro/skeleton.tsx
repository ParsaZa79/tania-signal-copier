import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  /** Offsets the shimmer sweep, for staggering a group of placeholders. */
  delayMs?: number;
}

/**
 * Shape-preserving placeholder with a shimmer sweep. The sweep runs on CSS
 * rather than Motion so it keeps animating in server-rendered markup, before
 * the JS bundle hydrates.
 */
export function Skeleton({ className, delayMs }: SkeletonProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-bg-tertiary/50",
        className
      )}
      aria-hidden="true"
    >
      <div
        className="animate-skeleton-shimmer absolute inset-y-0 left-0 w-[80%] bg-gradient-to-r from-transparent via-white/[0.06] to-transparent"
        style={delayMs ? { animationDelay: `${delayMs}ms` } : undefined}
      />
    </div>
  );
}
