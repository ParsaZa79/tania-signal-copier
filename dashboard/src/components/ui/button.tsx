import { cn } from "@/lib/utils";
import { forwardRef, type ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "secondary" | "danger" | "ghost" | "outline" | "accent";
  size?: "sm" | "md" | "lg" | "icon";
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-xl font-medium transition-all duration-200 focus:outline-none disabled:opacity-50 disabled:pointer-events-none",
          // Variants
          variant === "default" &&
            "bg-bg-elevated text-text-primary border border-border-default hover:bg-bg-tertiary hover:border-accent/30",
          variant === "secondary" &&
            "bg-bg-tertiary text-text-secondary hover:bg-bg-elevated hover:text-text-primary",
          variant === "danger" &&
            "bg-danger/10 text-danger border border-danger/20 hover:bg-danger/20 hover:border-danger/40",
          variant === "ghost" &&
            "bg-transparent text-text-secondary hover:bg-bg-tertiary hover:text-text-primary",
          variant === "outline" &&
            "border border-border-default bg-transparent text-text-secondary hover:bg-bg-tertiary hover:text-text-primary hover:border-accent/30",
          variant === "accent" &&
            "bg-gradient-to-r from-accent to-accent-dark text-bg-primary font-semibold hover:opacity-90 btn-glow",
          // Sizes
          size === "sm" && "h-8 px-3 text-xs gap-1.5",
          size === "md" && "h-10 px-4 text-sm gap-2",
          size === "lg" && "h-12 px-6 text-sm gap-2",
          size === "icon" && "h-9 w-9 p-0",
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button };
