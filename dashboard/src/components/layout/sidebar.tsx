"use client";

import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Activity,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleUserRound,
  History,
  House,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Repeat2,
  Settings,
  ShieldCheck,
  Sliders,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const SIDEBAR_EXPANDED_KEY = "signal-copier:sidebar-expanded";

const mobileNavItems = [
  { href: "/", label: "Home", icon: House },
  { href: "/copy-trading", label: "Copy", icon: Repeat2 },
  { href: "/orders", label: "Trade", icon: Plus },
];

const portfolioRoutes = [
  { href: "/positions", label: "Open positions", description: "Trades currently open", icon: Activity },
  { href: "/history", label: "Trade history", description: "Past trades and results", icon: History },
];

const accountRoutes = [
  { href: "/config", label: "Account setup", description: "Connection and trade settings", icon: Sliders },
  { href: "/access", label: "Access", description: "People and permissions", icon: ShieldCheck },
  { href: "/settings", label: "Settings", description: "Preferences and appearance", icon: Settings },
];

type MenuRoute = (typeof portfolioRoutes)[number] | (typeof accountRoutes)[number];
type MobileMenu = "portfolio" | "account";

export function isNavigationPathActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function CollapsedHint({ label, show }: { label: string; show: boolean }) {
  if (!show) return null;
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute left-[58px] top-1/2 z-[60] -translate-y-1/2 translate-x-1 whitespace-nowrap rounded-lg border border-border-default bg-bg-elevated px-2.5 py-1.5 text-[11px] font-medium text-text-primary opacity-0 shadow-lg transition-[opacity,transform] group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100"
    >
      {label}
    </span>
  );
}

function RailLabel({ collapsed, children }: { collapsed: boolean; children: ReactNode }) {
  return (
    <span
      className={cn(
        "block max-w-full overflow-hidden whitespace-nowrap transition-[max-height,opacity,transform] duration-[160ms] ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none",
        collapsed ? "max-h-0 -translate-y-1 opacity-0" : "max-h-5 translate-y-0 opacity-100"
      )}
    >
      {children}
    </span>
  );
}

interface SidebarProps {
  isConnected: boolean;
  accountName?: string;
  accountInitials?: string;
}

interface RailMenuProps {
  active: boolean;
  animate: boolean;
  collapsed: boolean;
  icon: ComponentType<{ className?: string }>;
  label: string;
  menuLabel: string;
  routes: readonly MenuRoute[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function RailMenu({ active, animate, collapsed, icon: Icon, label, menuLabel, routes, open, onOpenChange }: RailMenuProps) {
  const rootRef = useRef<HTMLLIElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onOpenChange(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [onOpenChange, open]);

  return (
    <li ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => onOpenChange(!open)}
        className={cn(
          "group relative flex flex-col items-center justify-center rounded-[12px] border font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 motion-reduce:transition-none",
          animate && "transition-[width,height,gap,background-color,border-color,color,box-shadow] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]",
          collapsed ? "h-12 w-12 gap-0" : "h-[82px] w-[76px] gap-2 text-[11px]",
          active || open
            ? "border-accent/30 bg-[linear-gradient(145deg,rgba(124,142,255,0.25),rgba(72,92,165,0.16))] text-text-primary shadow-[0_12px_32px_rgba(70,130,255,0.14)]"
            : "border-transparent text-text-muted hover:border-border-subtle hover:bg-bg-elevated/60 hover:text-text-primary"
        )}
      >
        <Icon className={cn("h-[19px] w-[19px] transition-colors", (active || open) && "text-accent")} />
        <RailLabel collapsed={collapsed}>{label}</RailLabel>
        <CollapsedHint label={label} show={collapsed && !open} />
      </button>

      {open ? (
        <div
          role="menu"
          aria-label={menuLabel}
          className={cn(
            "animate-fade-in absolute top-0 z-[60] max-h-[calc(100vh-2rem)] w-[270px] overflow-y-auto rounded-2xl border border-border-default bg-bg-secondary p-2 shadow-[0_24px_80px_rgba(0,0,0,0.72)] ring-1 ring-black/40",
            collapsed ? "left-[62px]" : "left-[90px]"
          )}
        >
          <p className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">{menuLabel}</p>
          {routes.map((route) => {
            const RouteIcon = route.icon;
            return (
              <Link
                role="menuitem"
                key={route.href}
                href={route.href}
                onClick={() => onOpenChange(false)}
                className="group flex items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-bg-elevated focus-visible:bg-bg-elevated focus-visible:outline-none"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border-subtle bg-bg-tertiary/70 text-text-secondary group-hover:text-accent">
                  <RouteIcon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1 text-left">
                  <span className="block text-sm font-medium text-text-primary">{route.label}</span>
                  <span className="mt-0.5 block text-[11px] text-text-muted">{route.description}</span>
                </span>
                <ChevronRight className="h-4 w-4 text-text-muted" />
              </Link>
            );
          })}
        </div>
      ) : null}
    </li>
  );
}

export function Sidebar({ isConnected, accountName = "Live Account", accountInitials }: SidebarProps) {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(true);
  const [animationEnabled, setAnimationEnabled] = useState(false);
  const [openMenu, setOpenMenu] = useState<"portfolio" | "account" | null>(null);
  const animationResetTimer = useRef<number | null>(null);
  const collapsed = !expanded;
  const initials = accountInitials || accountName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase())
    .join("") || "A";
  const copyActive = pathname.startsWith("/copy-trading");
  const tradeActive = isNavigationPathActive(pathname, "/orders");
  const portfolioActive = portfolioRoutes.some((route) => pathname.startsWith(route.href));
  const accountActive = accountRoutes.some((route) => pathname.startsWith(route.href));

  useEffect(() => {
    const stored = window.localStorage.getItem(SIDEBAR_EXPANDED_KEY);
    const frame = window.requestAnimationFrame(() => {
      if (stored !== null) setExpanded(stored === "true");
      animationResetTimer.current = window.setTimeout(() => setAnimationEnabled(true), 0);
    });
    return () => {
      window.cancelAnimationFrame(frame);
      if (animationResetTimer.current !== null) window.clearTimeout(animationResetTimer.current);
    };
  }, []);

  useEffect(() => {
    const toggleSidebar = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "b" || (!event.metaKey && !event.ctrlKey)) return;
      event.preventDefault();
      setAnimationEnabled(false);
      setExpanded((current) => {
        const next = !current;
        window.localStorage.setItem(SIDEBAR_EXPANDED_KEY, String(next));
        return next;
      });
      setOpenMenu(null);
      if (animationResetTimer.current !== null) window.clearTimeout(animationResetTimer.current);
      animationResetTimer.current = window.setTimeout(() => setAnimationEnabled(true), 0);
    };

    window.addEventListener("keydown", toggleSidebar);
    return () => window.removeEventListener("keydown", toggleSidebar);
  }, []);

  const handleExpandedChange = () => {
    setAnimationEnabled(true);
    setExpanded((current) => {
      const next = !current;
      window.localStorage.setItem(SIDEBAR_EXPANDED_KEY, String(next));
      return next;
    });
    setOpenMenu(null);
  };

  return (
    <aside
      data-collapsed={collapsed}
      data-animated={animationEnabled}
      className={cn(
        "sticky top-0 z-40 hidden h-screen shrink-0 flex-col items-center border-r border-border-subtle bg-bg-primary/82 backdrop-blur-xl will-change-[width] motion-reduce:transition-none md:flex",
        animationEnabled && "transition-[width] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]",
        collapsed ? "w-[72px]" : "w-[112px]"
      )}
    >
      <Link
        href="/"
        aria-label="Signal Copier home"
        className={cn(
          "mt-6 flex flex-col items-center rounded-xl px-2 py-1 text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 motion-reduce:transition-none",
          animationEnabled && "transition-[gap] duration-[160ms] ease-[cubic-bezier(0.23,1,0.32,1)]",
          collapsed ? "gap-0" : "gap-2"
        )}
      >
        <TrendingUp className="h-[26px] w-[26px] stroke-[1.65]" />
        <span className="text-[10px] font-semibold tracking-[-0.02em]">
          <RailLabel collapsed={collapsed}>Signal Copier</RailLabel>
        </span>
      </Link>

      <Button
        type="button"
        variant="outline"
        size="icon"
        aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
        aria-expanded={expanded}
        aria-controls="desktop-sidebar-navigation"
        aria-keyshortcuts="Meta+B Control+B"
        title={`${expanded ? "Collapse" : "Expand"} sidebar (⌘B / Ctrl+B)`}
        onClick={handleExpandedChange}
        className="absolute right-[-14px] top-[92px] z-40 h-7 w-7 rounded-full border-border-default bg-bg-secondary text-text-muted shadow-md transition-[transform,background-color,border-color,color] duration-[140ms] ease-[cubic-bezier(0.23,1,0.32,1)] hover:border-accent/30 hover:bg-bg-elevated hover:text-text-primary active:scale-[0.96] motion-reduce:transform-none motion-reduce:transition-none"
      >
        <span className="relative block h-3.5 w-3.5">
          <PanelLeftClose className={cn("absolute inset-0 h-3.5 w-3.5 transition-[opacity,transform] duration-[140ms] ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none", expanded ? "scale-100 rotate-0 opacity-100" : "scale-90 -rotate-12 opacity-0")} />
          <PanelLeftOpen className={cn("absolute inset-0 h-3.5 w-3.5 transition-[opacity,transform] duration-[140ms] ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none", expanded ? "scale-90 rotate-12 opacity-0" : "scale-100 rotate-0 opacity-100")} />
        </span>
      </Button>

      <nav id="desktop-sidebar-navigation" className={cn("flex-1 motion-reduce:transition-none", animationEnabled && "transition-[margin] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]", collapsed ? "mt-[72px]" : "mt-[58px]")} aria-label="Main navigation">
        <ul className={cn("flex flex-col items-center motion-reduce:transition-none", animationEnabled && "transition-[gap] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]", collapsed ? "gap-3" : "gap-4")}>
          <li>
            <Link
              href="/"
              aria-current={pathname === "/" ? "page" : undefined}
              className={cn(
                "group relative flex flex-col items-center justify-center rounded-[12px] border font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 motion-reduce:transition-none",
                animationEnabled && "transition-[width,height,gap,background-color,border-color,color,box-shadow] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]",
                collapsed ? "h-12 w-12 gap-0" : "h-[82px] w-[76px] gap-2 text-[11px]",
                pathname === "/"
                  ? "border-accent/30 bg-[linear-gradient(145deg,rgba(124,142,255,0.25),rgba(72,92,165,0.16))] text-text-primary shadow-[0_12px_32px_rgba(70,130,255,0.14)]"
                  : "border-transparent text-text-muted hover:border-border-subtle hover:bg-bg-elevated/60 hover:text-text-primary"
              )}
            >
              <House className={cn("h-[19px] w-[19px]", pathname === "/" && "text-accent")} />
              <RailLabel collapsed={collapsed}>Home</RailLabel>
              <CollapsedHint label="Home" show={collapsed} />
            </Link>
          </li>
          <li>
            <Link
              href="/copy-trading"
              aria-current={copyActive ? "page" : undefined}
              className={cn(
                "group relative flex flex-col items-center justify-center rounded-[12px] border font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 motion-reduce:transition-none",
                animationEnabled && "transition-[width,height,gap,background-color,border-color,color,box-shadow] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]",
                collapsed ? "h-12 w-12 gap-0" : "h-[82px] w-[76px] gap-2 text-[11px]",
                copyActive
                  ? "border-accent/30 bg-[linear-gradient(145deg,rgba(124,142,255,0.25),rgba(72,92,165,0.16))] text-text-primary shadow-[0_12px_32px_rgba(70,130,255,0.14)]"
                  : "border-transparent text-text-muted hover:border-border-subtle hover:bg-bg-elevated/60 hover:text-text-primary"
              )}
            >
              <Repeat2 className={cn("h-[19px] w-[19px]", copyActive && "text-accent")} />
              <RailLabel collapsed={collapsed}>Copy</RailLabel>
              <CollapsedHint label="Copy" show={collapsed} />
            </Link>
          </li>
          <li>
            <Link
              href="/orders"
              aria-current={tradeActive ? "page" : undefined}
              className={cn(
                "group relative flex flex-col items-center justify-center rounded-[12px] border font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 motion-reduce:transition-none",
                animationEnabled && "transition-[width,height,gap,background-color,border-color,color,box-shadow] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]",
                collapsed ? "h-12 w-12 gap-0" : "h-[82px] w-[76px] gap-2 text-[11px]",
                tradeActive
                  ? "border-accent/30 bg-[linear-gradient(145deg,rgba(124,142,255,0.25),rgba(72,92,165,0.16))] text-text-primary shadow-[0_12px_32px_rgba(70,130,255,0.14)]"
                  : "border-transparent text-text-muted hover:border-border-subtle hover:bg-bg-elevated/60 hover:text-text-primary"
              )}
            >
              <Plus className={cn("h-[19px] w-[19px]", tradeActive && "text-accent")} />
              <RailLabel collapsed={collapsed}>Trade</RailLabel>
              <CollapsedHint label="Trade" show={collapsed} />
            </Link>
          </li>
          <RailMenu
            active={portfolioActive}
            animate={animationEnabled}
            collapsed={collapsed}
            icon={BookOpen}
            label="Portfolio"
            menuLabel="Portfolio"
            routes={portfolioRoutes}
            open={openMenu === "portfolio"}
            onOpenChange={(open) => setOpenMenu(open ? "portfolio" : null)}
          />
          <RailMenu
            active={accountActive}
            animate={animationEnabled}
            collapsed={collapsed}
            icon={CircleUserRound}
            label="Account"
            menuLabel="Account"
            routes={accountRoutes}
            open={openMenu === "account"}
            onOpenChange={(open) => setOpenMenu(open ? "account" : null)}
          />
        </ul>
      </nav>

      <div className={cn("mb-5 border-t border-dashed border-border-subtle pt-4 motion-reduce:transition-none", animationEnabled && "transition-[width] duration-[180ms] ease-[cubic-bezier(0.77,0,0.175,1)]", collapsed ? "w-12" : "w-[88px]")}>
        <p className={cn("mb-3 flex items-center justify-center text-[9px] font-medium motion-reduce:transition-none", animationEnabled && "transition-[gap] duration-[160ms] ease-[cubic-bezier(0.23,1,0.32,1)]", collapsed ? "gap-0" : "gap-2", isConnected ? "text-success" : "text-danger")}>
          <span className={cn("h-1.5 w-1.5 rounded-full", isConnected ? "bg-success" : "bg-danger")} />
          <span className={cn("inline-block overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform] duration-[160ms] ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none", collapsed ? "max-w-0 -translate-x-1 opacity-0" : "max-w-[72px] translate-x-0 opacity-100")}>{isConnected ? "MT5 connected" : "MT5 offline"}</span>
        </p>
        <Link
          href="/config"
          title={accountName}
          className="group flex flex-col items-center rounded-2xl px-1 py-1.5 text-center transition-colors hover:bg-bg-elevated/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-full border border-border-default bg-bg-elevated text-[11px] font-semibold text-text-primary shadow-[0_8px_24px_rgba(0,0,0,0.28)]">
            {initials}
          </span>
          <span className={cn("mt-2 flex max-w-[86px] items-center gap-0.5 overflow-hidden text-[9px] font-medium text-text-secondary transition-[max-height,opacity,transform] duration-[160ms] ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none", collapsed ? "max-h-0 -translate-y-1 opacity-0" : "max-h-4 translate-y-0 opacity-100")}>
            <span className="truncate">{accountName}</span>
            <ChevronDown className="h-3 w-3 shrink-0" />
          </span>
        </Link>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const pathname = usePathname();
  const [openMenu, setOpenMenu] = useState<MobileMenu | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const portfolioTriggerRef = useRef<HTMLButtonElement>(null);
  const accountTriggerRef = useRef<HTMLButtonElement>(null);
  const portfolioActive = portfolioRoutes.some((route) =>
    isNavigationPathActive(pathname, route.href)
  );
  const accountActive = accountRoutes.some((route) => isNavigationPathActive(pathname, route.href));
  const menuRoutes = openMenu === "portfolio" ? portfolioRoutes : accountRoutes;
  const menuTitle = openMenu === "portfolio" ? "Portfolio" : "Account";

  useEffect(() => {
    if (!openMenu) return;

    const frame = window.requestAnimationFrame(() => {
      menuRef.current?.querySelector<HTMLElement>("a[href]")?.focus();
    });

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        const trigger =
          openMenu === "portfolio" ? portfolioTriggerRef.current : accountTriggerRef.current;
        setOpenMenu(null);
        window.requestAnimationFrame(() => trigger?.focus());
      }
    };
    const handleOutsidePress = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        menuRef.current?.contains(target) ||
        portfolioTriggerRef.current?.contains(target) ||
        accountTriggerRef.current?.contains(target)
      ) {
        return;
      }
      setOpenMenu(null);
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handleOutsidePress);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handleOutsidePress);
    };
  }, [openMenu]);

  const closeMenu = (restoreFocus = false) => {
    const closingMenu = openMenu;
    setOpenMenu(null);
    if (restoreFocus && closingMenu) {
      const trigger =
        closingMenu === "portfolio" ? portfolioTriggerRef.current : accountTriggerRef.current;
      window.requestAnimationFrame(() => trigger?.focus());
    }
  };

  const toggleMenu = (menu: MobileMenu) => {
    if (openMenu === menu) {
      closeMenu(true);
      return;
    }
    setOpenMenu(menu);
  };

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-50 border-t border-border-default bg-bg-primary/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl md:hidden"
      aria-label="Mobile navigation"
    >
      {openMenu ? (
        <div
          ref={menuRef}
          id={`mobile-${openMenu}-menu`}
          role="menu"
          aria-label={menuTitle}
          className="animate-fade-in fixed bottom-[calc(4.75rem+env(safe-area-inset-bottom))] right-3 z-10 max-h-[calc(100vh-6rem)] w-[calc(100vw-1.5rem)] max-w-[270px] overflow-y-auto rounded-2xl border border-border-default bg-bg-secondary p-2 shadow-[0_24px_80px_rgba(0,0,0,0.72)] ring-1 ring-black/40"
        >
          <p className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            {menuTitle}
          </p>
          {menuRoutes.map((route) => {
            const RouteIcon = route.icon;
            const active = isNavigationPathActive(pathname, route.href);
            return (
              <Link
                role="menuitem"
                key={route.href}
                href={route.href}
                aria-current={active ? "page" : undefined}
                onClick={() => closeMenu()}
                className={cn(
                  "group flex min-h-[56px] items-center gap-3 rounded-xl px-3 py-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70",
                  active ? "bg-bg-elevated" : "hover:bg-bg-elevated"
                )}
              >
                <span
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border-subtle bg-bg-tertiary/70 text-text-secondary",
                    active && "text-accent"
                  )}
                >
                  <RouteIcon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1 text-left">
                  <span className="block text-sm font-medium text-text-primary">{route.label}</span>
                  <span className="mt-0.5 block text-[11px] text-text-muted">{route.description}</span>
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-text-muted transition-transform group-hover:translate-x-0.5" />
              </Link>
            );
          })}
        </div>
      ) : null}

      <ul className="relative z-20 grid grid-cols-5 gap-1">
        {mobileNavItems.map((item) => {
          const Icon = item.icon;
          const active = isNavigationPathActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={() => closeMenu()}
                className={cn(
                  "flex min-h-[52px] flex-col items-center justify-center gap-1 rounded-xl px-1 text-[10px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70",
                  active ? "bg-bg-elevated text-text-primary" : "text-text-muted hover:bg-bg-elevated/60 hover:text-text-primary",
                  item.href === "/orders" && !active && "text-accent"
                )}
              >
                <Icon className={cn("h-[18px] w-[18px]", active && "text-accent")} />
                <span className="max-w-full truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
        <li>
          <button
            ref={portfolioTriggerRef}
            type="button"
            aria-expanded={openMenu === "portfolio"}
            aria-haspopup="menu"
            aria-controls="mobile-portfolio-menu"
            onClick={() => toggleMenu("portfolio")}
            className={cn(
              "flex min-h-[52px] w-full flex-col items-center justify-center gap-1 rounded-xl px-1 text-[10px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70",
              portfolioActive || openMenu === "portfolio"
                ? "bg-bg-elevated text-text-primary"
                : "text-text-muted hover:bg-bg-elevated/60 hover:text-text-primary"
            )}
          >
            <BookOpen
              className={cn(
                "h-[18px] w-[18px]",
                (portfolioActive || openMenu === "portfolio") && "text-accent"
              )}
            />
            <span className="max-w-full truncate">Portfolio</span>
          </button>
        </li>
        <li>
          <button
            ref={accountTriggerRef}
            type="button"
            aria-expanded={openMenu === "account"}
            aria-haspopup="menu"
            aria-controls="mobile-account-menu"
            onClick={() => toggleMenu("account")}
            className={cn(
              "flex min-h-[52px] w-full flex-col items-center justify-center gap-1 rounded-xl px-1 text-[10px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70",
              accountActive || openMenu === "account"
                ? "bg-bg-elevated text-text-primary"
                : "text-text-muted hover:bg-bg-elevated/60 hover:text-text-primary"
            )}
          >
            <CircleUserRound
              className={cn(
                "h-[18px] w-[18px]",
                (accountActive || openMenu === "account") && "text-accent"
              )}
            />
            <span className="max-w-full truncate">Account</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
