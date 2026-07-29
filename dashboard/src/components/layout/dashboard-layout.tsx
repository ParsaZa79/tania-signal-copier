"use client";

import { MobileNav, Sidebar } from "./sidebar";
import { CommandDeck, CommandSearchTrigger } from "./command-deck";
import { useAccessToken, useAuth } from "@workos-inc/authkit-nextjs/components";
import { SymbolIcon } from "@/components/dashboard/symbol-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWebSocket } from "@/hooks/use-websocket";
import {
  activateAccount,
  createAccount,
  getMe,
  getSymbolPrice,
} from "@/lib/api";
import { type AuthSession, setActiveAccountId } from "@/lib/auth-storage";
import { signOutAction } from "@/app/auth/actions";
import { ApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import type { Position, AccountInfo } from "@/types";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { SquareSnake } from "@/components/amicro/square-snake";
import { Bell, Search, ChevronDown, LogOut, Plus, UserRound } from "lucide-react";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  daily_change_percent?: number | null;
}

interface DashboardContextType {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  /** Still waiting on the first account report from the backend. */
  accountPending: boolean;
  error: string | null;
  reconnect: () => void;
  session: AuthSession;
  setSession: (session: AuthSession) => void;
  designPreview?: boolean;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardLayout");
  }
  return context;
}

interface DashboardLayoutProps {
  children: ReactNode;
}

const HEADER_SYMBOLS = [
  { base: "XAUUSD", label: "XAU/USD" },
  { base: "EURUSD", label: "EUR/USD" },
  { base: "GBPUSD", label: "GBP/USD" },
];

const subscribeToPreviewState = () => () => undefined;

function getHomePreviewState(): "connected" | "setup" | null {
  if (
    typeof window === "undefined" ||
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW !== "true" ||
    window.location.pathname !== "/"
  ) {
    return null;
  }

  return new URLSearchParams(window.location.search).get("previewHome") === "setup"
    ? "setup"
    : "connected";
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const homePreviewState = useSyncExternalStore(
    subscribeToPreviewState,
    getHomePreviewState,
    () => null
  );

  if (
    pathname.startsWith("/sign-in") ||
    pathname.startsWith("/sign-up") ||
    pathname.startsWith("/reset-password")
  ) {
    return <>{children}</>;
  }

  if (
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW === "true" &&
    pathname === "/"
  ) {
    if (!homePreviewState) {
      return (
        <main className="min-h-screen bg-bg-primary flex items-center justify-center">
          <p className="text-sm text-text-muted">Opening home preview…</p>
        </main>
      );
    }
    return (
      <DashboardPreviewLayout state={homePreviewState}>
        {children}
      </DashboardPreviewLayout>
    );
  }

  if (
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW === "true" &&
    (pathname === "/positions" ||
      pathname === "/history" ||
      pathname === "/orders" ||
      pathname === "/settings")
  ) {
    return (
      <DashboardPreviewLayout state="connected">
        {children}
      </DashboardPreviewLayout>
    );
  }

  if (
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW === "true" &&
    (pathname === "/config" || pathname === "/setup")
  ) {
    return (
      <DashboardPreviewLayout state={pathname === "/setup" ? "setup" : "connected"}>
        {children}
      </DashboardPreviewLayout>
    );
  }

  if (
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW === "true" &&
    pathname.startsWith("/copy-trading")
  ) {
    return <CopyTradingPreviewLayout>{children}</CopyTradingPreviewLayout>;
  }

  return <WorkOSDashboardLayout>{children}</WorkOSDashboardLayout>;
}

function CopyTradingPreviewLayout({ children }: DashboardLayoutProps) {
  const previewSession: AuthSession = {
    token: "design-preview",
    user: { id: "design-preview", email: "preview@example.com", role: "owner" },
    accounts: [
      { id: "preview-live", user_id: "design-preview", name: "Live Account", setup_complete: true },
      { id: "preview-growth", user_id: "design-preview", name: "Growth Account", setup_complete: true },
    ],
    activeAccountId: "preview-live",
    setupComplete: true,
  };
  const previewAccount: AccountInfo = {
    balance: 10_000,
    equity: 10_000,
    margin: 0,
    free_margin: 10_000,
    profit: 0,
  };

  return (
    <DashboardContext.Provider
      value={{
        positions: [],
        account: previewAccount,
        isConnected: true,
        accountPending: false,
        error: null,
        reconnect: () => undefined,
        session: previewSession,
        setSession: () => undefined,
      }}
    >
      <div className="flex min-h-screen bg-bg-primary">
        <Sidebar isConnected accountName="Live Account" accountInitials="LS" />
        <MobileNav />
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-border-subtle bg-bg-primary/90 px-5 backdrop-blur-xl lg:px-7">
            <div>
              <p className="text-sm font-semibold text-text-primary">Live Account</p>
              <p className="mt-0.5 text-[11px] text-success">MT5 connected</p>
            </div>
            <div className="hidden w-full max-w-sm items-center rounded-xl border border-border-subtle bg-bg-secondary/60 px-3 md:flex">
              <Search className="h-4 w-4 text-text-muted" />
              <span className="px-3 py-2.5 text-sm text-text-muted">Search symbols, tickets…</span>
            </div>
            <div className="rounded-xl border border-border-subtle bg-bg-secondary/55 px-3 py-2 text-sm text-text-secondary">
              Live Account
            </div>
          </header>
          <main className="p-4 pb-24 md:pb-4 lg:p-6">{children}</main>
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

function DashboardPreviewLayout({
  children,
  state,
}: DashboardLayoutProps & { state: "connected" | "setup" }) {
  const pathname = usePathname();
  const router = useRouter();
  const [commandOpen, setCommandOpen] = useState(false);
  const connected = state === "connected";
  const previewSession: AuthSession = {
    token: "design-preview",
    user: { id: "design-preview", email: "alex@example.com", role: "owner" },
    accounts: [
      {
        id: "preview-live",
        user_id: "design-preview",
        name: "Live Account",
        setup_complete: connected,
      },
    ],
    activeAccountId: "preview-live",
    setupComplete: connected,
  };
  const previewAccount: AccountInfo | null = connected
    ? {
        balance: 12_462.25,
        equity: 12_480.95,
        margin: 94.2,
        free_margin: 12_386.4,
        profit: 18.7,
      }
    : null;
  const previewPositions: Position[] = connected
    ? [
        {
          ticket: 1001,
          symbol: "XAUUSD",
          type: "buy",
          volume: 0.02,
          price_open: 2410,
          price_current: 2414.5,
          sl: 2398,
          tp: 2430,
          profit: 14.2,
          swap: 0,
          time: null,
        },
        {
          ticket: 1002,
          symbol: "EURUSD",
          type: "buy",
          volume: 0.05,
          price_open: 1.086,
          price_current: 1.087,
          sl: 0,
          tp: 1.094,
          profit: 4.5,
          swap: 0,
          time: null,
        },
      ]
    : [];

  return (
    <DashboardContext.Provider
      value={{
        positions: previewPositions,
        account: previewAccount,
        isConnected: connected,
        accountPending: false,
        error: null,
        reconnect: () => undefined,
        session: previewSession,
        setSession: () => undefined,
        designPreview: true,
      }}
    >
      <div className="flex min-h-screen bg-bg-primary">
        <Sidebar isConnected={connected} accountName="Live Account" accountInitials="LA" />
        <MobileNav />
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 flex h-[72px] items-center gap-4 border-b border-border-subtle bg-bg-primary/90 px-5 backdrop-blur-xl lg:px-7">
            <div>
              <p className="text-sm font-semibold text-text-primary">Live Account</p>
              <p className={cn("mt-0.5 text-[11px]", connected ? "text-success" : "text-text-muted")}>
                {connected ? "MT5 connected" : "Account setup required"}
              </p>
            </div>
            <CommandSearchTrigger onOpen={() => setCommandOpen(true)} />
            {connected && (
              <div className="hidden items-center gap-2 xl:flex">
                {HEADER_SYMBOLS.map((symbol) => (
                  <div
                    key={symbol.base}
                    className="flex items-center gap-2 rounded-xl border border-border-subtle bg-bg-secondary/55 px-2.5 py-1.5"
                  >
                    <SymbolIcon symbol={symbol.base} size="sm" className="h-7 w-7 rounded-lg" />
                    <span className="text-xs font-medium text-text-secondary">{symbol.label}</span>
                  </div>
                ))}
                <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-border-subtle bg-bg-secondary/55 text-text-muted">
                  <Bell className="h-4 w-4" />
                </span>
              </div>
            )}
            <div className="rounded-xl border border-border-subtle bg-bg-secondary/55 px-3 py-2 text-sm text-text-secondary">
              Live Account
            </div>
          </header>
          <main className="p-4 pb-24 md:pb-4 lg:p-6">{children}</main>
          <CommandDeck
            open={commandOpen}
            onOpenChange={setCommandOpen}
            pathname={pathname}
            positions={previewPositions}
            onConnectAccount={() => router.push("/config")}
          />
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

function WorkOSDashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const workosUserId = user?.id;
  const {
    accessToken,
    loading: tokenLoading,
    error: tokenError,
    getAccessToken,
  } = useAccessToken();
  const getAccessTokenRef = useRef(getAccessToken);
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessError, setAccessError] = useState<Error | null>(null);
  const [sessionAttempt, setSessionAttempt] = useState(0);

  useEffect(() => {
    getAccessTokenRef.current = getAccessToken;
  }, [getAccessToken]);

  useEffect(() => {
    if (authLoading || user) return;
    const search = window.location.search;
    const returnTo = `${pathname}${search}`;
    router.replace(`/sign-in?returnTo=${encodeURIComponent(returnTo)}`);
  }, [authLoading, pathname, router, user]);

  const setSession = useCallback((nextSession: AuthSession) => {
    setActiveAccountId(nextSession.activeAccountId);
    setSessionState(nextSession);
  }, []);

  useEffect(() => {
    if (authLoading || !workosUserId) return;

    let cancelled = false;

    async function loadSession() {
      setIsLoading(true);
      setAccessError(null);

      try {
        const token = await getAccessTokenRef.current();
        if (!token) throw new Error("Authentication required");

        const refreshed = await getMe(token);
        if (!cancelled) setSession(refreshed);
      } catch (error) {
        if (!cancelled) {
          setSessionState(null);
          setAccessError(
            error instanceof Error
              ? error
              : new Error("Dashboard access could not be verified"),
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadSession();
    return () => {
      cancelled = true;
    };
  }, [authLoading, sessionAttempt, setSession, workosUserId]);

  useEffect(() => {
    if (!accessToken) return;
    setSessionState((current) =>
      current && current.token !== accessToken ? { ...current, token: accessToken } : current
    );
  }, [accessToken]);

  if (authLoading || !user || tokenLoading || isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg-primary">
        <div
          className="flex flex-col items-center gap-4"
          role="status"
          aria-live="polite"
          aria-label={
            authLoading || user ? "Loading dashboard" : "Opening sign in"
          }
        >
          <SquareSnake />
          <p className="text-sm text-text-muted">
            {authLoading || user ? "Loading dashboard…" : "Opening sign in…"}
          </p>
        </div>
      </main>
    );
  }

  if (accessError || tokenError || !session) {
    const currentError = accessError || tokenError;
    const accessDisabled =
      currentError instanceof ApiError && currentError.code === "access_disabled";
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
        <div className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6">
          <p className="text-xs uppercase tracking-wider text-text-muted">Access</p>
          <h1 className="mt-2 text-xl font-semibold text-text-primary">
            {accessDisabled
              ? "This dashboard account is disabled"
              : "We couldn't finish setting up your dashboard"}
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            {accessDisabled
              ? "Your sign-in is valid, but an owner has disabled this account. Ask them to restore access before signing in again."
              : "Your sign-in succeeded. We couldn't create or load your dashboard profile, so no account data has been changed."}
          </p>
          {currentError && (
            <p className="mt-3 text-xs text-danger">
              {currentError.message}
            </p>
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            {!accessDisabled && (
              <Button
                variant="accent"
                onClick={() => setSessionAttempt((attempt) => attempt + 1)}
              >
                Try again
              </Button>
            )}
            <Button variant="outline" onClick={() => void signOutAction()}>
              Sign out
            </Button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <AuthenticatedDashboardLayout
      session={session}
      setSession={setSession}
      getAccessToken={getAccessToken}
      onLogout={signOutAction}
    >
      {children}
    </AuthenticatedDashboardLayout>
  );
}

function AuthenticatedDashboardLayout({
  children,
  session,
  setSession,
  getAccessToken,
  onLogout,
}: {
  children: ReactNode;
  session: AuthSession;
  setSession: (session: AuthSession) => void;
  getAccessToken: () => Promise<string | undefined>;
  onLogout?: () => Promise<void> | void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const isSetupRoute = pathname.startsWith("/setup");
  const needsSetup = !session.setupComplete || !session.activeAccountId;
  const shouldForceSetup = needsSetup && !isSetupRoute;
  const { positions, account, isConnected, hasSnapshot, error, reconnect } = useWebSocket({
    enabled: session.setupComplete && Boolean(session.activeAccountId),
    token: session.token,
    accountId: session.activeAccountId,
    getAccessToken,
  });
  const [headerPrices, setHeaderPrices] = useState<Record<string, PriceData>>({});
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [createAccountOpen, setCreateAccountOpen] = useState(false);
  const [newAccountName, setNewAccountName] = useState("");
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const completedAccounts = session.accounts.filter((item) => item.setup_complete);
  const activeAccount =
    completedAccounts.find((item) => item.id === session.activeAccountId) ??
    session.accounts.find((item) => item.id === session.activeAccountId) ??
    completedAccounts[0] ??
    session.accounts[0];
  const visibleActiveAccount = needsSetup ? null : activeAccount;
  const mt5Connected = isConnected && account !== null;
  // An error means the backend has effectively answered, so stop waiting.
  const accountPending = !hasSnapshot && error === null;

  useEffect(() => {
    if (shouldForceSetup) {
      router.replace("/setup");
    }
  }, [router, shouldForceSetup]);

  const fetchHeaderPrices = useCallback(async () => {
    if (!account) {
      setHeaderPrices({});
      return;
    }

    try {
      const results = await Promise.all(
        HEADER_SYMBOLS.map(async (sym) => {
          try {
            const price = await getSymbolPrice(sym.base);
            return { base: sym.base, data: price };
          } catch {
            return null;
          }
        })
      );

      setHeaderPrices(() => {
        const newPrices: Record<string, PriceData> = {};
        results.forEach((result) => {
          if (result?.data) {
            newPrices[result.base] = result.data;
          }
        });
        return newPrices;
      });
    } catch (err) {
      console.error("Failed to fetch header prices:", err);
    }
  }, [account]);

  useEffect(() => {
    const initialFetch = setTimeout(fetchHeaderPrices, 0);
    const interval = setInterval(fetchHeaderPrices, 2000);
    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
  }, [fetchHeaderPrices, session.activeAccountId]);

  const handleSwitchAccount = async (accountId: string) => {
    const result = await activateAccount(accountId);
    const nextSession = {
      ...session,
      accounts: result.accounts,
      activeAccountId: result.active_account_id,
    };
    setHeaderPrices({});
    setSession(nextSession);
    setAccountMenuOpen(false);
  };

  const handleCreateAccountSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newAccountName.trim();
    if (!name) return;

    setIsCreatingAccount(true);
    setAccountError(null);
    try {
      const created = await createAccount(name);
      const activated = await activateAccount(created.account.id);
      setSession({
        ...session,
        accounts: activated.accounts,
        activeAccountId: activated.active_account_id,
        setupComplete: false,
      });
      setHeaderPrices({});
      setNewAccountName("");
      setCreateAccountOpen(false);
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : "Could not create account");
    } finally {
      setIsCreatingAccount(false);
    }
  };

  const handleLogout = async () => {
    if (onLogout) {
      await onLogout();
      return;
    }
    await signOutAction();
  };

  if (shouldForceSetup) {
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center">
        <p className="text-sm text-text-muted">Opening account setup...</p>
      </main>
    );
  }

  return (
    <DashboardContext.Provider
      value={{ positions, account, isConnected: mt5Connected, accountPending, error, reconnect, session, setSession }}
    >
      <div className="flex min-h-screen">
        <Sidebar
          isConnected={mt5Connected}
          accountName={visibleActiveAccount?.name || (needsSetup ? "Account Setup" : "Live Account")}
        />
        <MobileNav />

        <div className="min-w-0 flex-1 flex flex-col min-h-screen">
          <header className="h-14 border-b border-border-subtle bg-bg-primary/70 backdrop-blur-xl sticky top-0 z-40">
            <div className="h-full px-4 lg:px-6 flex items-center justify-between gap-4">
              <div className="min-w-0 sm:w-28 sm:shrink-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {visibleActiveAccount?.name || (needsSetup ? "Account Setup" : "Portfolio")}
                </p>
                <p className="text-[11px] text-text-muted truncate hidden sm:block">
                  {needsSetup
                    ? "Account setup required"
                    : mt5Connected
                    ? "Markets active · Live MT5 feed"
                    : "Waiting for MT5 connection"}
                </p>
              </div>

              <CommandSearchTrigger onOpen={() => setCommandOpen(true)} />

              <div className="flex items-center gap-4">
                <div className="hidden min-[1400px]:flex items-center gap-3">
                  {!needsSetup && HEADER_SYMBOLS.map((sym) => {
                    const price = headerPrices[sym.base];

                    if (!price) {
                      return (
                        <div
                          key={sym.base}
                          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border-subtle bg-bg-tertiary/80"
                        >
                          <SymbolIcon
                            symbol={sym.base}
                            size="sm"
                            className="w-7 h-7 rounded-md"
                          />
                          <span className="text-xs font-medium text-text-secondary">
                            {sym.label}
                          </span>
                          <span className="text-xs text-text-muted tabular-nums animate-pulse">
                            ---
                          </span>
                        </div>
                      );
                    }

                    const change = price.daily_change_percent ?? 0;

                    return (
                      <MarketPill
                        key={sym.base}
                        symbol={sym.label}
                        iconSymbol={sym.base}
                        value={price.bid.toFixed(price.bid > 100 ? 2 : 5)}
                        change={change}
                      />
                    );
                  })}
                </div>

                <button className="relative w-9 h-9 rounded-xl bg-bg-tertiary/80 border border-border-subtle flex items-center justify-center hover:bg-bg-elevated transition-colors">
                  <Bell className="w-4 h-4 text-text-secondary" />
                  {mt5Connected && (
                    <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-success rounded-full" />
                  )}
                </button>

                <div className="relative">
                  <button
                    onClick={() => setAccountMenuOpen((open) => !open)}
                    className="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-xl bg-bg-tertiary/80 border border-border-subtle hover:bg-bg-elevated transition-colors"
                  >
                    <div className="w-7 h-7 rounded-lg bg-bg-elevated border border-border-default flex items-center justify-center">
                      <UserRound className="w-3.5 h-3.5 text-text-primary" />
                    </div>
                    <div className="text-left hidden lg:block max-w-36">
                      <p className="text-xs font-medium text-text-primary truncate">
                        {visibleActiveAccount?.name || session.user.email}
                      </p>
                    </div>
                    <ChevronDown className="w-3.5 h-3.5 text-text-muted hidden lg:block" />
                  </button>

                  {accountMenuOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setAccountMenuOpen(false)}
                      />
                      <div className="absolute right-0 top-full mt-2 w-64 p-2 rounded-xl bg-bg-elevated border border-border-subtle shadow-lg z-20">
                        <div className="px-3 py-2 border-b border-border-subtle mb-1">
                          <p className="text-xs font-medium text-text-primary truncate">
                            {session.user.email}
                          </p>
                        </div>
                        {completedAccounts.length === 0 && (
                          <div className="px-3 py-2 text-xs text-text-muted">
                            No configured accounts yet.
                          </div>
                        )}
                        {completedAccounts.map((item) => (
                          <button
                            key={item.id}
                            onClick={() => handleSwitchAccount(item.id)}
                            className={`w-full px-3 py-2 text-left text-sm rounded-lg transition-colors ${
                              item.id === session.activeAccountId
                                ? "bg-accent/20 text-accent"
                                : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                            }`}
                          >
                            {item.name}
                          </button>
                        ))}
                        <div className="border-t border-border-subtle mt-2 pt-2 space-y-1">
                          {session.setupComplete && (
                            <button
                              onClick={() => {
                                setAccountMenuOpen(false);
                                setCreateAccountOpen(true);
                              }}
                              className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-bg-tertiary hover:text-text-primary rounded-lg transition-colors flex items-center gap-2"
                            >
                              <Plus className="w-4 h-4" />
                              New account
                            </button>
                          )}
                          <button
                            onClick={handleLogout}
                            className="w-full px-3 py-2 text-left text-sm text-danger hover:bg-danger/10 rounded-lg transition-colors flex items-center gap-2"
                          >
                            <LogOut className="w-4 h-4" />
                            Sign out
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </header>

          <main className="flex-1 overflow-auto p-4 pb-24 md:pb-4 lg:p-6">
            {error && (
              <div className="mb-6 p-4 rounded-xl bg-danger/10 border border-danger/30 flex items-center justify-between animate-fade-in">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-danger/20 flex items-center justify-center">
                    <span className="text-danger font-bold">!</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-danger">Connection Error</p>
                    <p className="text-xs text-text-muted">{error}</p>
                  </div>
                </div>
                <button
                  onClick={reconnect}
                  className="px-4 py-2 rounded-lg bg-danger/20 text-sm font-medium text-danger hover:bg-danger/30 transition-colors"
                >
                  Reconnect
                </button>
              </div>
            )}
            {children}
          </main>

          <CommandDeck
            open={commandOpen}
            onOpenChange={setCommandOpen}
            pathname={pathname}
            positions={positions}
            onConnectAccount={() => setCreateAccountOpen(true)}
          />

          {createAccountOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
              <form
                onSubmit={handleCreateAccountSubmit}
                className="w-full max-w-sm rounded-xl border border-border-subtle bg-bg-elevated p-5 shadow-xl"
              >
                <div className="mb-4">
                  <p className="text-sm font-semibold text-text-primary">New Account</p>
                  <p className="text-xs text-text-muted mt-1">
                    Create an isolated MT5 trading account.
                  </p>
                </div>
                <Input
                  label="Account Name"
                  value={newAccountName}
                  onChange={(event) => setNewAccountName(event.target.value)}
                  placeholder="Broker account"
                  autoFocus
                />
                {accountError && (
                  <div className="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2">
                    <p className="text-xs text-danger">{accountError}</p>
                  </div>
                )}
                <div className="mt-5 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setCreateAccountOpen(false);
                      setNewAccountName("");
                      setAccountError(null);
                    }}
                    disabled={isCreatingAccount}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="accent"
                    disabled={isCreatingAccount || !newAccountName.trim()}
                  >
                    {isCreatingAccount && <IOSSpinner size={16} />}
                    <span>Create</span>
                  </Button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

function MarketPill({
  symbol,
  iconSymbol,
  value,
  change,
}: {
  symbol: string;
  iconSymbol: string;
  value: string;
  change: number;
}) {
  const isPositive = change >= 0;

  return (
    <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border-subtle bg-bg-tertiary/80">
      <SymbolIcon symbol={iconSymbol} size="sm" className="w-7 h-7 rounded-md" />
      <span className="text-xs font-medium text-text-secondary">{symbol}</span>
      <span className="text-xs font-medium text-text-primary tabular-nums">{value}</span>
      <span
        className={`text-[10px] font-semibold tabular-nums px-1.5 py-0.5 rounded ${
          isPositive ? "bg-success/15 text-success" : "bg-danger/15 text-danger"
        }`}
      >
        {isPositive ? "↑" : "↓"} {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  );
}
