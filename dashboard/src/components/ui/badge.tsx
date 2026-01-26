import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "danger" | "warning" | "info" | "accent";
  size?: "sm" | "md";
}

export function Badge({
  className,
  variant = "default",
  size = "md",
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center font-semibold rounded-lg",
        // Size
        size === "sm" && "px-2 py-0.5 text-[10px]",
        size === "md" && "px-2.5 py-1 text-xs",
        // Variants with proper Tailwind colors
        variant === "default" &&
          "bg-bg-tertiary text-text-secondary border border-border-subtle",
        variant === "success" &&
          "bg-success/15 text-success border border-success/30",
        variant === "danger" &&
          "bg-danger/15 text-danger border border-danger/30",
        variant === "warning" &&
          "bg-warning/15 text-warning border border-warning/30",
        variant === "info" &&
          "bg-info/15 text-info border border-info/30",
        variant === "accent" &&
          "bg-accent/15 text-accent border border-accent/30",
        className
      )}
      {...props}
    />
  );
}
