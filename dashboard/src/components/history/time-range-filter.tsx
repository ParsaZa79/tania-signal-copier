"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  Calendar,
  ChevronDown,
  Clock,
  CalendarDays,
  CalendarRange,
} from "lucide-react";

export type TimePreset =
  | "today"
  | "yesterday"
  | "this_week"
  | "this_month"
  | "custom"
  | "all";

export interface DateRange {
  from: string | null;
  to: string | null;
}

interface TimeRangeFilterProps {
  value: TimePreset;
  dateRange: DateRange;
  onChange: (preset: TimePreset, range: DateRange) => void;
}

const presets: { id: TimePreset; label: string; icon: React.ReactNode }[] = [
  { id: "all", label: "All Time", icon: <Clock className="w-3.5 h-3.5" /> },
  { id: "today", label: "Today", icon: <Calendar className="w-3.5 h-3.5" /> },
  {
    id: "yesterday",
    label: "Yesterday",
    icon: <CalendarDays className="w-3.5 h-3.5" />,
  },
  {
    id: "this_week",
    label: "This Week",
    icon: <CalendarRange className="w-3.5 h-3.5" />,
  },
  {
    id: "this_month",
    label: "This Month",
    icon: <CalendarRange className="w-3.5 h-3.5" />,
  },
];

function getPresetDates(preset: TimePreset): DateRange {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  switch (preset) {
    case "today":
      return {
        from: today.toISOString().split("T")[0],
        to: tomorrow.toISOString().split("T")[0],
      };
    case "yesterday": {
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      return {
        from: yesterday.toISOString().split("T")[0],
        to: today.toISOString().split("T")[0],
      };
    }
    case "this_week": {
      const weekStart = new Date(today);
      const dayOfWeek = today.getDay();
      const diff = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Monday as start
      weekStart.setDate(today.getDate() - diff);
      return {
        from: weekStart.toISOString().split("T")[0],
        to: tomorrow.toISOString().split("T")[0],
      };
    }
    case "this_month": {
      const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
      return {
        from: monthStart.toISOString().split("T")[0],
        to: tomorrow.toISOString().split("T")[0],
      };
    }
    case "all":
    default:
      return { from: null, to: null };
  }
}

export function TimeRangeFilter({
  value,
  dateRange,
  onChange,
}: TimeRangeFilterProps) {
  const [showCustom, setShowCustom] = useState(false);
  const [customFrom, setCustomFrom] = useState(dateRange.from || "");
  const [customTo, setCustomTo] = useState(dateRange.to || "");
  const customRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        customRef.current &&
        !customRef.current.contains(event.target as Node)
      ) {
        setShowCustom(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handlePresetClick = (preset: TimePreset) => {
    if (preset === "custom") {
      setShowCustom(true);
    } else {
      setShowCustom(false);
      const range = getPresetDates(preset);
      onChange(preset, range);
    }
  };

  const handleCustomApply = () => {
    if (customFrom) {
      const toDate = customTo || new Date().toISOString().split("T")[0];
      onChange("custom", { from: customFrom, to: toDate });
      setShowCustom(false);
    }
  };

  const formatDisplayDate = (dateStr: string | null) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Preset Buttons - Segmented Control Style */}
      <div className="inline-flex p-1 rounded-xl bg-bg-tertiary/60 backdrop-blur-sm border border-border-subtle">
        {presets.map((preset, idx) => {
          const isActive = value === preset.id;
          return (
            <button
              key={preset.id}
              onClick={() => handlePresetClick(preset.id)}
              className={cn(
                "relative px-3.5 py-2 text-xs font-medium rounded-lg transition-all duration-200 flex items-center gap-1.5",
                "focus:outline-none focus:ring-2 focus:ring-accent/30 focus:ring-offset-1 focus:ring-offset-bg-tertiary",
                isActive
                  ? "bg-gradient-to-b from-bg-elevated to-bg-tertiary text-text-primary shadow-sm border border-border-default"
                  : "text-text-muted hover:text-text-secondary hover:bg-bg-elevated/50",
                idx === 0 && "rounded-l-lg",
                idx === presets.length - 1 && "rounded-r-lg"
              )}
            >
              <span
                className={cn(
                  "transition-colors duration-200",
                  isActive ? "text-accent" : "text-text-muted"
                )}
              >
                {preset.icon}
              </span>
              <span className="hidden sm:inline">{preset.label}</span>
            </button>
          );
        })}
      </div>

      {/* Custom Date Range Button & Dropdown */}
      <div className="relative" ref={customRef}>
        <button
          onClick={() => setShowCustom(!showCustom)}
          className={cn(
            "flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium transition-all duration-200",
            "border focus:outline-none focus:ring-2 focus:ring-accent/30",
            value === "custom"
              ? "bg-accent/10 border-accent/30 text-accent"
              : "bg-bg-tertiary/60 border-border-subtle text-text-muted hover:text-text-secondary hover:border-border-default"
          )}
        >
          <CalendarRange className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">
            {value === "custom" && dateRange.from
              ? `${formatDisplayDate(dateRange.from)} - ${formatDisplayDate(dateRange.to)}`
              : "Custom Range"}
          </span>
          <ChevronDown
            className={cn(
              "w-3.5 h-3.5 transition-transform duration-200",
              showCustom && "rotate-180"
            )}
          />
        </button>

        {/* Custom Date Picker Dropdown */}
        {showCustom && (
          <div
            className={cn(
              "absolute top-full right-0 mt-2 z-50",
              "w-72 p-4 rounded-2xl",
              "bg-bg-elevated/95 backdrop-blur-xl",
              "border border-border-default shadow-lg",
              "animate-fade-in"
            )}
          >
            {/* Decorative header line */}
            <div className="absolute top-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

            <div className="space-y-4">
              <div className="flex items-center gap-2 text-text-primary">
                <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
                  <CalendarRange className="w-4 h-4 text-accent" />
                </div>
                <span className="font-medium text-sm">Custom Date Range</span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-[10px] uppercase tracking-wider text-text-muted mb-1.5 font-medium">
                    From
                  </label>
                  <input
                    type="date"
                    value={customFrom}
                    onChange={(e) => setCustomFrom(e.target.value)}
                    className={cn(
                      "w-full px-3 py-2.5 rounded-xl text-sm",
                      "bg-bg-tertiary/80 border border-border-subtle",
                      "text-text-primary placeholder:text-text-muted",
                      "focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/20",
                      "transition-all duration-200",
                      "[color-scheme:dark]"
                    )}
                  />
                </div>

                <div>
                  <label className="block text-[10px] uppercase tracking-wider text-text-muted mb-1.5 font-medium">
                    To
                  </label>
                  <input
                    type="date"
                    value={customTo}
                    onChange={(e) => setCustomTo(e.target.value)}
                    className={cn(
                      "w-full px-3 py-2.5 rounded-xl text-sm",
                      "bg-bg-tertiary/80 border border-border-subtle",
                      "text-text-primary placeholder:text-text-muted",
                      "focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/20",
                      "transition-all duration-200",
                      "[color-scheme:dark]"
                    )}
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => setShowCustom(false)}
                  className={cn(
                    "flex-1 px-4 py-2.5 rounded-xl text-xs font-medium",
                    "bg-bg-tertiary text-text-secondary",
                    "border border-border-subtle",
                    "hover:bg-bg-elevated hover:text-text-primary",
                    "transition-all duration-200"
                  )}
                >
                  Cancel
                </button>
                <button
                  onClick={handleCustomApply}
                  disabled={!customFrom}
                  className={cn(
                    "flex-1 px-4 py-2.5 rounded-xl text-xs font-semibold",
                    "bg-gradient-to-r from-accent to-accent-dark text-bg-primary",
                    "hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed",
                    "transition-all duration-200",
                    "shadow-sm hover:shadow-md hover:shadow-accent/10"
                  )}
                >
                  Apply Range
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
