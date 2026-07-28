"use client";

import { SquareSnake } from "@/components/amicro/square-snake";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className
      )}
    >
      <div className="min-w-0">
        {meta && (
          <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-text-muted">
            {meta}
          </div>
        )}
        <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-text-muted mt-1">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 shrink-0">{actions}</div>
      )}
    </div>
  );
}

interface PageLoadingProps {
  label?: string;
  className?: string;
}

export function PageLoading({
  label = "Loading…",
  className,
}: PageLoadingProps) {
  return (
    <div
      className={cn(
        "flex min-h-[360px] flex-col items-center justify-center gap-4",
        className
      )}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <SquareSnake />
      <p className="text-sm text-text-muted">{label}</p>
    </div>
  );
}
