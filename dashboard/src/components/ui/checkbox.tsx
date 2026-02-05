"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import { forwardRef, type InputHTMLAttributes } from "react";

export interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, disabled, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <label
        htmlFor={inputId}
        className={cn(
          "inline-flex items-center gap-3 cursor-pointer group",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            type="checkbox"
            disabled={disabled}
            className="peer sr-only"
            {...props}
          />
          <div
            className={cn(
              "w-5 h-5 rounded-md border-2 transition-all duration-200",
              "border-border-default bg-bg-tertiary",
              "peer-focus-visible:ring-2 peer-focus-visible:ring-accent/30",
              "peer-checked:bg-accent peer-checked:border-accent",
              "group-hover:border-accent/50",
              className
            )}
          >
            <Check
              className={cn(
                "w-full h-full p-0.5 text-bg-primary stroke-[3]",
                "opacity-0 scale-0 transition-all duration-150",
                "peer-checked:opacity-100 peer-checked:scale-100"
              )}
            />
          </div>
        </div>
        {label && (
          <span className="text-sm text-text-secondary group-hover:text-text-primary transition-colors">
            {label}
          </span>
        )}
      </label>
    );
  }
);

Checkbox.displayName = "Checkbox";

export { Checkbox };
