"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  TrendingUp,
  History,
  Settings,
  Activity,
  Plus,
  Zap,
  Bot,
  Sliders,
  BarChart3,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard, color: "accent" as const },
  { href: "/bot", label: "Bot Control", icon: Bot, color: "success" as const },
  { href: "/config", label: "Configuration", icon: Sliders, color: "info" as const },
  { href: "/positions", label: "Positions", icon: Activity, color: "warning" as const },
  { href: "/analysis", label: "Analysis", icon: BarChart3, color: "accent" as const },
  { href: "/orders", label: "New Order", icon: Plus, color: "muted" as const },
  { href: "/history", label: "History", icon: History, color: "muted" as const },
  { href: "/settings", label: "Settings", icon: Settings, color: "muted" as const },
];

const colorStyles = {
  accent: { bg: "bg-accent/20", text: "text-accent", activeBg: "bg-accent" },
  info: { bg: "bg-info/20", text: "text-info", activeBg: "bg-info" },
  success: { bg: "bg-success/20", text: "text-success", activeBg: "bg-success" },
  warning: { bg: "bg-warning/20", text: "text-warning", activeBg: "bg-warning" },
  muted: { bg: "bg-bg-tertiary", text: "text-text-muted", activeBg: "bg-accent" },
};

interface SidebarProps {
  isConnected: boolean;
}

export function Sidebar({ isConnected }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="w-[260px] h-screen flex flex-col border-r border-border-subtle bg-bg-secondary/50 backdrop-blur-xl sticky top-0">
      {/* Logo */}
      <div className="p-6 pb-8 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-accent to-accent-dark flex items-center justify-center shadow-lg shadow-accent/20">
              <TrendingUp className="w-6 h-6 text-bg-primary" />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-success rounded-full border-2 border-bg-secondary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-text-primary tracking-tight">
              TradingBot
            </h1>
            <p className="text-xs text-text-muted">MT5 Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation - scrollable if content overflows */}
      <nav className="flex-1 px-3 overflow-y-auto min-h-0">
        <div className="mb-2 px-3">
          <span className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
            Menu
          </span>
        </div>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            const colors = colorStyles[item.color];

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 relative",
                    isActive
                      ? "bg-gradient-to-r from-accent/20 to-accent/5 text-accent border border-accent/30"
                      : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                  )}
                >
                  {/* Active indicator bar */}
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-accent" />
                  )}
                  <div
                    className={cn(
                      "w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-200",
                      isActive
                        ? `${colors.activeBg} shadow-lg`
                        : `${colors.bg} group-hover:bg-bg-elevated`
                    )}
                  >
                    <Icon
                      className={cn(
                        "w-[18px] h-[18px]",
                        isActive ? "text-bg-primary" : colors.text
                      )}
                    />
                  </div>
                  <span className={cn("font-medium text-sm", isActive && "font-semibold")}>{item.label}</span>
                  {isActive && (
                    <div className="ml-auto w-2 h-2 rounded-full bg-accent animate-pulse" />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bottom section - always visible */}
      <div className="flex-shrink-0">
        {/* Quick Actions */}
        <div className="px-3 mb-4">
          <button className="w-full group flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-accent/15 to-accent/5 border border-accent/30 hover:border-accent/50 transition-all duration-200">
            <div className="w-9 h-9 rounded-lg bg-accent/30 flex items-center justify-center">
              <Zap className="w-[18px] h-[18px] text-accent" />
            </div>
            <div className="text-left">
              <span className="block text-sm font-medium text-text-primary">
                Quick Trade
              </span>
              <span className="text-[10px] text-text-muted">
                Execute instantly
              </span>
            </div>
          </button>
        </div>

        {/* Connection Status */}
        <div className="p-4 mx-3 mb-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-text-secondary">
              Connection
            </span>
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "relative flex h-2.5 w-2.5 rounded-full",
                  isConnected ? "bg-success" : "bg-danger"
                )}
              >
                {isConnected && (
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
                )}
              </span>
              <span
                className={cn(
                  "text-xs font-semibold",
                  isConnected ? "text-success" : "text-danger"
                )}
              >
                {isConnected ? "Online" : "Offline"}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  isConnected
                    ? "w-full bg-gradient-to-r from-success/60 to-success"
                    : "w-0 bg-danger"
                )}
              />
            </div>
          </div>
          <p className="mt-2 text-[10px] text-text-muted">
            {isConnected ? "MT5 Terminal Active" : "Connecting to MT5..."}
          </p>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border-subtle">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent/40 to-accent/20 flex items-center justify-center">
              <span className="text-sm font-semibold text-accent">P</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary truncate">
                Pro Account
              </p>
              <p className="text-[10px] text-text-muted">AMarkets-Real</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
