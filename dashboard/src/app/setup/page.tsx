"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Info,
  LockKeyhole,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { PageLoading } from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { AnimatedSection, PageContainer } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  activateAccount,
  completeAccountSetup,
  connectMT5,
  createAccount,
  getMT5BrokerServers,
  getAccountRuntimeConfig,
  getMe,
  saveAccountRuntimeConfig,
} from "@/lib/api";
import {
  type BrokerBrandGroup,
  brokerBrandForServer,
  brokerServerKind,
  groupBrokerServers,
} from "@/lib/broker-brands";
import {
  MT5_BROKER_SERVER_OPTIONS,
  type BrokerServerOption,
} from "@/lib/broker-servers";
import { cn } from "@/lib/utils";

const EMPTY_CONFIG = {
  MT5_LOGIN: "",
  MT5_PASSWORD: "",
  MT5_SERVER: "",
};

const SETUP_STEPS = [
  { title: "Broker", description: "Choose your broker" },
  { title: "Account type", description: "Select Live or Demo" },
  { title: "Login details", description: "Enter your credentials" },
  { title: "Test connection", description: "Verify account access" },
] as const;

const BROKER_PAGE_SIZE = 8;
const ALL_SEEDED_BROKER_GROUPS = groupBrokerServers(MT5_BROKER_SERVER_OPTIONS);
const INITIAL_BROKER_GROUPS = ALL_SEEDED_BROKER_GROUPS.slice(0, BROKER_PAGE_SIZE);

type SetupConfig = typeof EMPTY_CONFIG;
type AccountKind = "live" | "demo";
type VerifiedConnection = {
  accountName: string;
  login: string;
  server: string;
};

function maskMt5Login(login: string) {
  const visible = login.trim().slice(-4);
  return visible ? `••••${visible}` : "••••";
}

function seededBrokerGroupForServer(server: string): BrokerBrandGroup | undefined {
  const brand = brokerBrandForServer(server);
  if (!brand) return undefined;
  const seededGroup = ALL_SEEDED_BROKER_GROUPS.find((group) => group.id === brand.id);
  if (!server || seededGroup?.servers.some((option) => option.value === server)) {
    return seededGroup;
  }
  return {
    ...(seededGroup ?? brand),
    servers: [
      ...(seededGroup?.servers ?? []),
      { value: server, label: server, source: "current" },
    ],
  };
}

function paginateBrokerGroups(
  groups: BrokerBrandGroup[],
  page: number,
  query: string
) {
  const normalizedQuery = query.trim().toLowerCase();
  const filteredGroups = normalizedQuery
    ? groups.filter(
        (brand) =>
          brand.name.toLowerCase().includes(normalizedQuery) ||
          brand.servers.some(
            (server) =>
              server.label.toLowerCase().includes(normalizedQuery) ||
              server.value.toLowerCase().includes(normalizedQuery)
        )
      )
    : groups;
  const start = (page - 1) * BROKER_PAGE_SIZE;
  return {
    groups: filteredGroups.slice(start, start + BROKER_PAGE_SIZE),
    total: filteredGroups.length,
    totalPages: Math.ceil(filteredGroups.length / BROKER_PAGE_SIZE),
  };
}

function localBrokerPage(page: number, query: string) {
  return paginateBrokerGroups(ALL_SEEDED_BROKER_GROUPS, page, query);
}

export function AccountSetupContent({ editMode = false }: { editMode?: boolean }) {
  const router = useRouter();
  const { session, setSession, designPreview } = useDashboard();
  const [step, setStep] = useState(1);
  const [accountName, setAccountName] = useState("Live Account");
  const [config, setConfig] = useState<SetupConfig>(EMPTY_CONFIG);
  const [configuredSecrets, setConfiguredSecrets] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(session.activeAccountId && !designPreview));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [brokerServers, setBrokerServers] = useState<BrokerServerOption[]>(
    INITIAL_BROKER_GROUPS.flatMap((brand) => brand.servers)
  );
  const [brokerQuery, setBrokerQuery] = useState("");
  const [debouncedBrokerQuery, setDebouncedBrokerQuery] = useState("");
  const [brokerPage, setBrokerPage] = useState(1);
  const [brokerTotal, setBrokerTotal] = useState(ALL_SEEDED_BROKER_GROUPS.length);
  const [brokerTotalPages, setBrokerTotalPages] = useState(
    Math.ceil(ALL_SEEDED_BROKER_GROUPS.length / BROKER_PAGE_SIZE)
  );
  const [isBrokerLoading, setIsBrokerLoading] = useState(false);
  const [brokerLoadError, setBrokerLoadError] = useState<string | null>(null);
  const [selectedBrand, setSelectedBrand] = useState<BrokerBrandGroup>();
  const [accountKind, setAccountKind] = useState<AccountKind>("live");
  const [useCustomBrokerServer, setUseCustomBrokerServer] = useState(false);
  const [verifiedConnection, setVerifiedConnection] = useState<VerifiedConnection | null>(null);
  const [enteredWithCompletedSetup] = useState(
    () => !editMode && !designPreview && session.setupComplete
  );

  const activeAccount = useMemo(
    () => session.accounts.find((account) => account.id === session.activeAccountId),
    [session.accounts, session.activeAccountId]
  );
  const brokerGroups = useMemo(() => groupBrokerServers(brokerServers), [brokerServers]);
  const matchingServers = useMemo(
    () =>
      selectedBrand?.servers.filter(
        (server) => brokerServerKind(server.value) === accountKind
      ) ?? [],
    [accountKind, selectedBrand]
  );

  useEffect(() => {
    if (activeAccount?.name) setAccountName(activeAccount.name);
  }, [activeAccount?.name]);

  useEffect(() => {
    if (enteredWithCompletedSetup) router.replace("/");
  }, [enteredWithCompletedSetup, router]);

  useEffect(() => {
    if (designPreview) {
      setConfig({ MT5_LOGIN: "3370267", MT5_PASSWORD: "", MT5_SERVER: "AMarkets-Real" });
      setConfiguredSecrets(["MT5_PASSWORD"]);
      setSelectedBrand(seededBrokerGroupForServer("AMarkets-Real"));
      setAccountKind("live");
      setIsLoading(false);
      return;
    }

    if (!session.activeAccountId) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    async function loadConfig() {
      setIsLoading(true);
      try {
        const result = await getAccountRuntimeConfig();
        if (cancelled || !result.success) return;
        const nextConfig = {
          MT5_LOGIN: result.config.MT5_LOGIN || "",
          MT5_PASSWORD: result.config.MT5_PASSWORD || "",
          MT5_SERVER: result.config.MT5_SERVER || "",
        };
        const currentBrand = brokerBrandForServer(nextConfig.MT5_SERVER);
        setConfig(nextConfig);
        setConfiguredSecrets(result.configuredSecrets || []);
        setAccountKind(brokerServerKind(nextConfig.MT5_SERVER));
        setSelectedBrand(
          currentBrand ? seededBrokerGroupForServer(nextConfig.MT5_SERVER) : undefined
        );
        setUseCustomBrokerServer(Boolean(nextConfig.MT5_SERVER && !currentBrand));
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load setup state");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadConfig();
    return () => {
      cancelled = true;
    };
  }, [designPreview, session.activeAccountId]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedBrokerQuery(brokerQuery.trim());
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [brokerQuery]);

  useEffect(() => {
    if (designPreview) {
      const result = localBrokerPage(brokerPage, debouncedBrokerQuery);
      setBrokerServers(result.groups.flatMap((brand) => brand.servers));
      setBrokerTotal(result.total);
      setBrokerTotalPages(result.totalPages);
      setBrokerLoadError(null);
      return;
    }

    let cancelled = false;
    setIsBrokerLoading(true);
    setBrokerLoadError(null);
    getMT5BrokerServers({
      page: brokerPage,
      pageSize: BROKER_PAGE_SIZE,
      query: debouncedBrokerQuery,
    })
      .then((result) => {
        if (cancelled || !result.success) return;
        const hasPaginationMetadata =
          Number.isInteger(result.total) && Number.isInteger(result.total_pages);
        const fallbackPage = hasPaginationMetadata
          ? null
          : paginateBrokerGroups(
              groupBrokerServers(result.brokers),
              brokerPage,
              debouncedBrokerQuery
            );
        const nextGroups = fallbackPage?.groups ?? groupBrokerServers(result.brokers);
        setBrokerServers(
          fallbackPage
            ? fallbackPage.groups.flatMap((brand) => brand.servers)
            : result.brokers
        );
        setBrokerTotal(fallbackPage?.total ?? result.total);
        setBrokerTotalPages(fallbackPage?.totalPages ?? result.total_pages);
        setSelectedBrand((previous) =>
          previous
            ? nextGroups.find((brand) => brand.id === previous.id) ?? previous
            : previous
        );
      })
      .catch((loadError) => {
        if (!cancelled) {
          setBrokerLoadError(
            loadError instanceof Error ? loadError.message : "Could not load brokers"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setIsBrokerLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [brokerPage, debouncedBrokerQuery, designPreview]);

  const updateField = (key: keyof SetupConfig, value: string) => {
    setConfig((previous) => ({ ...previous, [key]: value }));
    setError(null);
    setMessage(null);
  };

  const chooseBroker = (brand: BrokerBrandGroup) => {
    setSelectedBrand(brand);
    setUseCustomBrokerServer(false);
    const existingBelongsToBrand = brand.servers.some(
      (server) => server.value === config.MT5_SERVER
    );
    if (!existingBelongsToBrand) updateField("MT5_SERVER", "");
  };

  const chooseManualBroker = () => {
    setSelectedBrand(undefined);
    setUseCustomBrokerServer(true);
    updateField("MT5_SERVER", "");
    setStep(2);
  };

  const updateBrokerSearch = (value: string) => {
    setBrokerQuery(value);
    setBrokerPage(1);
  };

  const chooseAccountKind = (kind: AccountKind) => {
    setAccountKind(kind);
    const available = selectedBrand?.servers.filter(
      (server) => brokerServerKind(server.value) === kind
    ) ?? [];
    const currentStillMatches = available.some(
      (server) => server.value === config.MT5_SERVER
    );
    updateField(
      "MT5_SERVER",
      currentStillMatches ? config.MT5_SERVER : available.length === 1 ? available[0].value : ""
    );
  };

  const goToStep = (nextStep: number) => {
    setError(null);
    setMessage(null);
    setStep(nextStep);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const continueFromBroker = () => {
    if (!selectedBrand && !useCustomBrokerServer) {
      setError("Choose the broker where you opened your trading account.");
      return;
    }
    goToStep(2);
  };

  const continueFromAccountType = () => {
    if (!config.MT5_SERVER.trim()) {
      setError(
        useCustomBrokerServer
          ? "Enter the exact server name shown in MetaTrader 5."
          : "Choose the server shown for this account in MetaTrader 5."
      );
      return;
    }
    goToStep(3);
  };

  const continueFromLogin = () => {
    const missing: string[] = [];
    if (!session.activeAccountId && !accountName.trim()) missing.push("account name");
    if (!config.MT5_LOGIN.trim() || Number.isNaN(Number(config.MT5_LOGIN))) {
      missing.push("MT5 login number");
    }
    if (!config.MT5_PASSWORD.trim() && !configuredSecrets.includes("MT5_PASSWORD")) {
      missing.push("MT5 password");
    }
    if (missing.length > 0) {
      setError(`Add your ${missing.join(" and ")} to continue.`);
      return;
    }
    goToStep(4);
  };

  const validateAll = () => {
    const missing: string[] = [];
    if (!session.activeAccountId && !accountName.trim()) missing.push("account name");
    if (!config.MT5_LOGIN.trim() || Number.isNaN(Number(config.MT5_LOGIN))) {
      missing.push("MT5 login");
    }
    if (!config.MT5_PASSWORD.trim() && !configuredSecrets.includes("MT5_PASSWORD")) {
      missing.push("MT5 password");
    }
    if (!config.MT5_SERVER.trim()) missing.push("broker server");
    return missing;
  };

  const handleSubmit = async () => {
    const missing = validateAll();
    if (missing.length > 0) {
      setError(`Missing required setup: ${missing.join(", ")}.`);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setMessage("Saving your account details…");

    if (designPreview) {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      setMessage("Account details saved and the broker connection was verified.");
      setVerifiedConnection({
        accountName,
        login: config.MT5_LOGIN,
        server: config.MT5_SERVER,
      });
      setIsSubmitting(false);
      return;
    }

    try {
      if (!session.activeAccountId) {
        const created = await createAccount(accountName.trim());
        const activated = await activateAccount(created.account.id);
        setSession({
          ...session,
          accounts: activated.accounts,
          activeAccountId: activated.active_account_id,
          setupComplete: false,
        });
      }

      const saved = await saveAccountRuntimeConfig(config);
      setConfiguredSecrets(saved.configuredSecrets || []);

      setMessage("Testing the broker connection…");
      const mt5Result = await connectMT5(config);
      if (!mt5Result.success || !mt5Result.connected) {
        throw new Error(mt5Result.error || mt5Result.health?.error || "Broker connection failed");
      }

      setMessage("Finishing account setup…");
      await completeAccountSetup();
      const refreshed = await getMe(session.token);
      setVerifiedConnection({
        accountName,
        login: config.MT5_LOGIN,
        server: config.MT5_SERVER,
      });
      setSession(refreshed);
      setMessage("Account details saved and the broker connection was verified.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not complete setup");
      setMessage(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        <PageLoading label="Loading account setup…" />
      </PageContainer>
    );
  }

  return (
    <>
      <PageContainer className="mx-auto max-w-[1120px] pb-10">
        <AnimatedSection>
          <SetupProgress currentStep={step} onStepChange={goToStep} />
        </AnimatedSection>

        <AnimatedSection className="space-y-6">
          {step === 1 && (
            <BrokerStep
              brokerQuery={brokerQuery}
              brokerGroups={brokerGroups}
              brokerPage={brokerPage}
              brokerTotal={brokerTotal}
              brokerTotalPages={brokerTotalPages}
              isBrokerLoading={isBrokerLoading}
              brokerLoadError={brokerLoadError}
              selectedBrand={selectedBrand}
              setBrokerQuery={updateBrokerSearch}
              setBrokerPage={setBrokerPage}
              chooseBroker={chooseBroker}
              chooseManualBroker={chooseManualBroker}
            />
          )}

          {step === 2 && (
            <AccountTypeStep
              accountKind={accountKind}
              config={config}
              matchingServers={matchingServers}
              selectedBrand={selectedBrand}
              useCustomBrokerServer={useCustomBrokerServer}
              chooseAccountKind={chooseAccountKind}
              updateField={updateField}
            />
          )}

          {step === 3 && (
            <LoginStep
              accountName={accountName}
              config={config}
              configuredSecrets={configuredSecrets}
              hasExistingAccount={Boolean(session.activeAccountId)}
              isSubmitting={isSubmitting}
              setAccountName={setAccountName}
              updateField={updateField}
            />
          )}

          {step === 4 && (
            <ReviewStep
              accountKind={accountKind}
              accountName={accountName}
              config={config}
              selectedBrand={selectedBrand}
              useCustomBrokerServer={useCustomBrokerServer}
            />
          )}

          {(error || message) && <SetupNotice error={error} message={message} />}

          <SetupFooter
            step={step}
            isSubmitting={isSubmitting}
            canContinue={Boolean(selectedBrand || useCustomBrokerServer)}
            onBack={() => (step === 1 ? router.push("/") : goToStep(step - 1))}
            onContinue={
              step === 1
                ? continueFromBroker
                : step === 2
                  ? continueFromAccountType
                  : step === 3
                    ? continueFromLogin
                    : handleSubmit
            }
            editMode={editMode}
          />
        </AnimatedSection>
      </PageContainer>

      <ConnectionVerifiedDialog
        connection={verifiedConnection}
        selectedBrand={selectedBrand}
        onOpenDashboard={() => router.replace("/")}
        onStayInSettings={() => {
          if (editMode) {
            setVerifiedConnection(null);
          } else {
            router.replace("/config");
          }
        }}
      />
    </>
  );
}

function ConnectionVerifiedDialog({
  connection,
  selectedBrand,
  onOpenDashboard,
  onStayInSettings,
}: {
  connection: VerifiedConnection | null;
  selectedBrand?: BrokerBrandGroup;
  onOpenDashboard: () => void;
  onStayInSettings: () => void;
}) {
  return (
    <Dialog
      open={Boolean(connection)}
      onOpenChange={() => undefined}
      backdropClassName="bg-black/50 backdrop-blur-none"
    >
      <DialogContent className="w-[calc(100%-2rem)] max-w-[520px] overflow-hidden border-border-default bg-[#151517]/95 shadow-[0_28px_90px_rgba(0,0,0,0.68)] backdrop-blur-2xl">
        {connection && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="connection-verified-title"
            aria-describedby="connection-verified-description"
            className="px-6 py-8 text-center sm:py-9"
          >
            <span className="mx-auto flex h-[72px] w-[72px] items-center justify-center rounded-full border border-success/45 bg-success/[0.08] text-success shadow-[0_0_28px_rgba(52,199,89,0.12)]">
              <ShieldCheck className="h-9 w-9" strokeWidth={1.7} />
            </span>
            <h2
              id="connection-verified-title"
              className="mt-6 text-[28px] font-semibold tracking-[-0.035em] text-text-primary"
            >
              Connection verified
            </h2>
            <p
              id="connection-verified-description"
              className="mx-auto mt-2 max-w-md text-sm leading-6 text-text-secondary"
            >
              {connection.accountName} is connected to {connection.server} and ready to use.
            </p>

            <div className="mt-6 flex min-h-[88px] items-center gap-4 rounded-2xl border border-border-default bg-bg-primary/35 p-4 text-left">
              {selectedBrand ? (
                <BrokerLogo brand={selectedBrand} size="sm" />
              ) : (
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border-subtle bg-bg-tertiary text-accent">
                  <Server className="h-5 w-5" />
                </span>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-text-primary">{connection.server}</p>
                <p className="mt-0.5 font-mono text-xs text-text-muted">
                  {maskMt5Login(connection.login)}
                </p>
              </div>
              <span className="inline-flex shrink-0 items-center gap-2 text-sm font-medium text-success">
                <span className="h-1.5 w-1.5 rounded-full bg-success" />
                Connected
              </span>
            </div>

            <Button
              type="button"
              variant="accent"
              size="lg"
              autoFocus
              onClick={onOpenDashboard}
              className="mt-5 h-[52px] w-full bg-accent-dark text-white hover:bg-accent"
            >
              Open dashboard
            </Button>
            <button
              type="button"
              onClick={onStayInSettings}
              className="mt-4 text-sm font-medium text-accent hover:text-accent-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              Stay in account settings
            </button>
            <p className="mt-5 text-xs leading-5 text-text-muted">
              You can update or retest this connection later from Settings.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function SetupPage() {
  return <AccountSetupContent />;
}

function SetupProgress({
  currentStep,
  onStepChange,
}: {
  currentStep: number;
  onStepChange: (step: number) => void;
}) {
  const activeStep = SETUP_STEPS[currentStep - 1];
  return (
    <nav aria-label="Account setup progress" className="pt-2 sm:pt-6">
      <div className="sm:hidden">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-accent">Step {currentStep} of {SETUP_STEPS.length}</p>
            <p className="mt-1 text-base font-semibold text-text-primary">{activeStep.title}</p>
            <p className="text-xs text-text-muted">{activeStep.description}</p>
          </div>
          <span className="text-xs text-text-muted">{Math.round((currentStep / SETUP_STEPS.length) * 100)}%</span>
        </div>
        <div className="mt-3 grid grid-cols-4 gap-1.5" aria-hidden="true">
          {SETUP_STEPS.map((item, index) => (
            <span key={item.title} className={cn("h-1 rounded-full", index < currentStep ? "bg-accent" : "bg-bg-elevated")} />
          ))}
        </div>
      </div>

      <ol className="hidden gap-4 sm:grid sm:grid-cols-2 xl:grid-cols-4 xl:gap-0">
        {SETUP_STEPS.map((item, index) => {
          const number = index + 1;
          const active = number === currentStep;
          const completed = number < currentStep;
          return (
            <li key={item.title} className="relative flex min-w-0 items-center gap-3 xl:pr-8">
              <button
                type="button"
                onClick={() => completed && onStepChange(number)}
                disabled={!completed}
                aria-current={active ? "step" : undefined}
                aria-label={completed ? `Go back to ${item.title}` : `${number}. ${item.title}`}
                className={cn(
                  "relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-sm",
                  active && "border-accent bg-accent/10 text-accent",
                  completed && "border-success/40 bg-success/10 text-success",
                  !active && !completed && "border-border-default text-text-muted"
                )}
              >
                {completed ? <Check className="h-4 w-4" /> : number}
              </button>
              <span className="min-w-0">
                <span className={cn("block text-sm font-medium", active ? "text-accent" : "text-text-secondary")}>
                  {item.title}
                </span>
                <span className="mt-0.5 block truncate text-xs text-text-muted">{item.description}</span>
              </span>
              {index < SETUP_STEPS.length - 1 && (
                <span className="absolute left-[calc(100%-1.5rem)] right-2 top-5 hidden border-t border-dashed border-border-default xl:block" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function BrokerStep({
  brokerQuery,
  brokerGroups,
  brokerPage,
  brokerTotal,
  brokerTotalPages,
  isBrokerLoading,
  brokerLoadError,
  selectedBrand,
  setBrokerQuery,
  setBrokerPage,
  chooseBroker,
  chooseManualBroker,
}: {
  brokerQuery: string;
  brokerGroups: BrokerBrandGroup[];
  brokerPage: number;
  brokerTotal: number;
  brokerTotalPages: number;
  isBrokerLoading: boolean;
  brokerLoadError: string | null;
  selectedBrand?: BrokerBrandGroup;
  setBrokerQuery: (value: string) => void;
  setBrokerPage: (page: number) => void;
  chooseBroker: (brand: BrokerBrandGroup) => void;
  chooseManualBroker: () => void;
}) {
  const firstBrokerNumber = brokerTotal === 0 ? 0 : (brokerPage - 1) * BROKER_PAGE_SIZE + 1;
  const lastBrokerNumber = Math.min(brokerPage * BROKER_PAGE_SIZE, brokerTotal);

  return (
    <section aria-labelledby="choose-broker-title" className="space-y-6">
      <div>
        <h1 id="choose-broker-title" className="text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl">
          Choose your broker
        </h1>
        <p className="mt-2 text-base text-text-secondary">
          Search for the company where you opened your trading account.
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-border-default bg-bg-secondary/70 px-4 py-3 text-sm text-text-secondary">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <p>This is not choosing an investment. You are only connecting an account so Signal Copier can copy trades.</p>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" />
        <input
          type="search"
          value={brokerQuery}
          onChange={(event) => setBrokerQuery(event.target.value)}
          placeholder="Search brokers"
          aria-label="Search brokers"
          className="h-14 w-full rounded-xl border border-border-default bg-bg-secondary pl-12 pr-4 text-base text-text-primary outline-none placeholder:text-text-muted focus:border-accent/60 focus:ring-2 focus:ring-accent/10"
        />
      </div>

      {brokerGroups.length > 0 ? (
        <div
          className={cn(
            "grid h-[310px] grid-cols-2 auto-rows-[132px] content-start gap-3 overflow-y-auto pr-1 transition-opacity sm:auto-rows-[120px] sm:gap-4 lg:grid-cols-4",
            isBrokerLoading && "pointer-events-none opacity-50"
          )}
          aria-busy={isBrokerLoading}
        >
          {brokerGroups.map((brand) => {
            const selected = selectedBrand?.id === brand.id;
            return (
              <button
                key={brand.id}
                type="button"
                aria-pressed={selected}
                onClick={() => chooseBroker(brand)}
                className={cn(
                  "group relative flex h-full flex-col items-start justify-center gap-3 rounded-xl border bg-bg-secondary px-4 py-3 text-left outline-none sm:flex-row sm:items-center sm:justify-start sm:gap-4 sm:px-5 sm:py-4",
                  "hover:border-border-default hover:bg-bg-tertiary focus-visible:ring-2 focus-visible:ring-accent/40",
                  selected ? "border-accent bg-accent/[0.04]" : "border-border-subtle"
                )}
              >
                <BrokerLogo brand={brand} />
                <span className="min-w-0 max-w-full text-sm font-medium leading-5 text-text-primary sm:flex-1 sm:truncate sm:text-base">{brand.name}</span>
                <span
                  className={cn(
                    "absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full border",
                    selected ? "border-accent bg-accent text-bg-primary" : "border-text-muted text-transparent"
                  )}
                >
                  <Check className="h-3.5 w-3.5" />
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="rounded-xl border border-border-subtle px-5 py-8 text-center">
          {isBrokerLoading ? (
            <div className="flex items-center justify-center gap-2 text-sm text-text-secondary">
              <IOSSpinner size={16} />
              Loading brokers…
            </div>
          ) : (
            <>
              <p className="text-base font-medium text-text-primary">No broker found</p>
              <p className="mt-1 text-sm text-text-secondary">Try another spelling or enter the server manually.</p>
            </>
          )}
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-text-secondary" aria-live="polite">
            {brokerTotal > 0
              ? `${firstBrokerNumber}–${lastBrokerNumber} of ${brokerTotal} brokers`
              : "0 brokers"}
          </p>
          {brokerLoadError && (
            <p className="mt-1 text-xs text-danger">Could not refresh the broker directory.</p>
          )}
        </div>
        {brokerTotalPages > 1 && (
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setBrokerPage(brokerPage - 1)}
              disabled={brokerPage <= 1 || isBrokerLoading}
              aria-label="Previous broker page"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Previous
            </Button>
            <span className="min-w-20 text-center text-xs text-text-muted">
              Page {brokerPage} of {brokerTotalPages}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setBrokerPage(brokerPage + 1)}
              disabled={brokerPage >= brokerTotalPages || isBrokerLoading}
              aria-label="Next broker page"
            >
              Next
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      <div className="grid gap-5 border-y border-border-subtle py-5 md:grid-cols-2 md:divide-x md:divide-border-subtle">
        <button type="button" onClick={chooseManualBroker} className="flex items-center gap-4 text-left">
          <span className="flex h-10 w-10 items-center justify-center rounded-full border border-border-default text-text-secondary">
            <Settings2 className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-base font-medium text-text-primary">My broker isn’t listed</span>
            <span className="mt-0.5 block text-sm text-text-muted">Enter the exact MT5 server manually</span>
          </span>
        </button>

        <div className="flex min-h-12 items-center gap-4 md:pl-6">
          {selectedBrand ? (
            <>
              <BrokerLogo brand={selectedBrand} size="sm" />
              <span>
                <span className="block text-xs text-text-muted">Selected broker</span>
                <span className="mt-0.5 block text-base font-medium text-text-primary">{selectedBrand.name}</span>
                <span className="block text-xs text-text-muted">Server will be selected next</span>
              </span>
            </>
          ) : (
            <span className="text-sm text-text-muted">Choose a broker above to continue.</span>
          )}
        </div>
      </div>
    </section>
  );
}

function AccountTypeStep({
  accountKind,
  config,
  matchingServers,
  selectedBrand,
  useCustomBrokerServer,
  chooseAccountKind,
  updateField,
}: {
  accountKind: AccountKind;
  config: SetupConfig;
  matchingServers: BrokerServerOption[];
  selectedBrand?: BrokerBrandGroup;
  useCustomBrokerServer: boolean;
  chooseAccountKind: (kind: AccountKind) => void;
  updateField: (key: keyof SetupConfig, value: string) => void;
}) {
  const hasLive = selectedBrand?.servers.some((server) => brokerServerKind(server.value) === "live") ?? true;
  const hasDemo = selectedBrand?.servers.some((server) => brokerServerKind(server.value) === "demo") ?? true;

  return (
    <section aria-labelledby="account-type-title" className="space-y-7">
      <div className="flex items-center gap-4">
        {selectedBrand && <BrokerLogo brand={selectedBrand} size="sm" />}
        <div>
          <p className="text-sm text-accent">{selectedBrand?.name ?? "Broker entered manually"}</p>
          <h1 id="account-type-title" className="mt-1 text-3xl font-semibold tracking-[-0.03em] text-text-primary">
            Choose the account type
          </h1>
          <p className="mt-2 text-base text-text-secondary">Use the same type and server name shown in MetaTrader 5.</p>
        </div>
      </div>

      {useCustomBrokerServer ? (
        <div className="max-w-2xl rounded-2xl border border-border-default bg-bg-secondary p-6">
          <Input
            label="Exact MT5 server name"
            value={config.MT5_SERVER}
            onChange={(event) => updateField("MT5_SERVER", event.target.value)}
            placeholder="Example: BrokerName-Live01"
            autoFocus
          />
          <p className="mt-3 text-sm text-text-muted">In MT5, open Accounts and copy the server name exactly as it appears.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <AccountKindCard
              active={accountKind === "live"}
              disabled={!hasLive}
              icon={<WalletCards className="h-5 w-5" />}
              title="Live account"
              description="Trades use the real funds in your broker account."
              onClick={() => chooseAccountKind("live")}
            />
            <AccountKindCard
              active={accountKind === "demo"}
              disabled={!hasDemo}
              icon={<ShieldCheck className="h-5 w-5" />}
              title="Demo account"
              description="Practice with virtual funds supplied by your broker."
              onClick={() => chooseAccountKind("demo")}
            />
          </div>

          <div>
            <h2 className="text-lg font-semibold text-text-primary">Choose the exact server</h2>
            <p className="mt-1 text-sm text-text-secondary">If several servers are listed, match the name shown in MT5.</p>
            <div className="mt-4 divide-y divide-border-subtle rounded-2xl border border-border-default bg-bg-secondary">
              {matchingServers.length > 0 ? (
                matchingServers.map((server) => {
                  const selected = server.value === config.MT5_SERVER;
                  return (
                    <button
                      key={server.value}
                      type="button"
                      onClick={() => updateField("MT5_SERVER", server.value)}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left first:rounded-t-2xl last:rounded-b-2xl hover:bg-bg-tertiary"
                    >
                      <span className={cn("flex h-5 w-5 items-center justify-center rounded-full border", selected ? "border-accent" : "border-text-muted")}>
                        {selected && <span className="h-2.5 w-2.5 rounded-full bg-accent" />}
                      </span>
                      <span className="flex-1">
                        <span className="block text-sm font-medium text-text-primary">{server.label}</span>
                        <span className="mt-0.5 block text-xs text-text-muted">Server ID: {server.value}</span>
                      </span>
                    </button>
                  );
                })
              ) : (
                <div className="px-5 py-6 text-sm text-text-secondary">This broker has no {accountKind} server in the current directory.</div>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function LoginStep({
  accountName,
  config,
  configuredSecrets,
  hasExistingAccount,
  isSubmitting,
  setAccountName,
  updateField,
}: {
  accountName: string;
  config: SetupConfig;
  configuredSecrets: string[];
  hasExistingAccount: boolean;
  isSubmitting: boolean;
  setAccountName: (value: string) => void;
  updateField: (key: keyof SetupConfig, value: string) => void;
}) {
  return (
    <section aria-labelledby="login-details-title" className="space-y-7">
      <div>
        <h1 id="login-details-title" className="text-3xl font-semibold tracking-[-0.03em] text-text-primary">Enter your MT5 login</h1>
        <p className="mt-2 text-base text-text-secondary">Use the login number and trading password from your broker—not your dashboard password.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-5 rounded-2xl border border-border-default bg-bg-secondary p-6 sm:p-8">
          <Input
            label="Account name"
            value={accountName}
            onChange={(event) => setAccountName(event.target.value)}
            disabled={hasExistingAccount || isSubmitting}
            placeholder="Live Account"
          />
          <Input
            label="MT5 login number"
            inputMode="numeric"
            value={config.MT5_LOGIN}
            onChange={(event) => updateField("MT5_LOGIN", event.target.value)}
            placeholder="Example: 3370267"
            disabled={isSubmitting}
          />
          <Input
            label="Trading password"
            type="password"
            value={config.MT5_PASSWORD}
            onChange={(event) => updateField("MT5_PASSWORD", event.target.value)}
            placeholder={configuredSecrets.includes("MT5_PASSWORD") ? "Password already saved" : "Enter trading password"}
            disabled={isSubmitting}
          />
        </div>

        <aside className="space-y-5 rounded-2xl border border-border-subtle p-6">
          <LockKeyhole className="h-6 w-6 text-success" />
          <div>
            <h2 className="text-base font-semibold text-text-primary">Your credentials stay private</h2>
            <p className="mt-2 text-sm leading-6 text-text-secondary">They are encrypted for this dashboard account and are never shown to traders you copy.</p>
          </div>
          <div className="border-t border-border-subtle pt-5 text-sm text-text-secondary">
            <p className="font-medium text-text-primary">Where to find the login</p>
            <p className="mt-1">Open MetaTrader 5, then look under Accounts in the Navigator.</p>
          </div>
        </aside>
      </div>
    </section>
  );
}

function ReviewStep({
  accountKind,
  accountName,
  config,
  selectedBrand,
  useCustomBrokerServer,
}: {
  accountKind: AccountKind;
  accountName: string;
  config: SetupConfig;
  selectedBrand?: BrokerBrandGroup;
  useCustomBrokerServer: boolean;
}) {
  return (
    <section aria-labelledby="review-connection-title" className="space-y-7">
      <div>
        <h1 id="review-connection-title" className="text-3xl font-semibold tracking-[-0.03em] text-text-primary">Review and test the connection</h1>
        <p className="mt-2 text-base text-text-secondary">We’ll save the details, connect to MT5, and tell you clearly if anything needs attention.</p>
      </div>

      <div className="divide-y divide-border-subtle rounded-2xl border border-border-default bg-bg-secondary">
        <ReviewRow
          icon={selectedBrand ? <BrokerLogo brand={selectedBrand} size="sm" /> : <Server className="h-5 w-5 text-accent" />}
          label="Broker"
          value={selectedBrand?.name ?? (useCustomBrokerServer ? "Broker entered manually" : "—")}
        />
        <ReviewRow icon={<WalletCards className="h-5 w-5 text-accent" />} label="Account" value={`${accountName} · ${accountKind === "live" ? "Live" : "Demo"}`} />
        <ReviewRow icon={<Server className="h-5 w-5 text-success" />} label="MT5 server" value={config.MT5_SERVER} />
        <ReviewRow icon={<ShieldCheck className="h-5 w-5 text-success" />} label="MT5 login" value={config.MT5_LOGIN} />
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-success/20 bg-success/[0.06] px-4 py-3 text-sm text-text-secondary">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
        <p>Testing the connection does not place a trade. It only verifies that this dashboard can reach the selected MT5 account.</p>
      </div>
    </section>
  );
}

function AccountKindCard({
  active,
  disabled,
  icon,
  title,
  description,
  onClick,
}: {
  active: boolean;
  disabled: boolean;
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        "flex min-h-32 items-start gap-4 rounded-2xl border bg-bg-secondary p-5 text-left outline-none",
        active ? "border-accent bg-accent/[0.04]" : "border-border-subtle hover:border-border-default",
        disabled && "cursor-not-allowed opacity-40"
      )}
    >
      <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl", active ? "bg-accent/15 text-accent" : "bg-bg-tertiary text-text-secondary")}>{icon}</span>
      <span>
        <span className="block text-base font-semibold text-text-primary">{title}</span>
        <span className="mt-1 block text-sm leading-6 text-text-secondary">{description}</span>
        {disabled && <span className="mt-2 block text-xs text-text-muted">No matching server listed</span>}
      </span>
    </button>
  );
}

function ReviewRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="grid gap-3 px-5 py-4 sm:grid-cols-[180px_1fr] sm:items-center">
      <div className="flex items-center gap-3 text-sm text-text-muted">
        <span className="flex h-10 w-10 items-center justify-center">{icon}</span>
        {label}
      </div>
      <p className="break-words text-sm font-medium text-text-primary">{value}</p>
    </div>
  );
}

function BrokerLogo({ brand, size = "md" }: { brand: Pick<BrokerBrandGroup, "name" | "logo">; size?: "sm" | "md" }) {
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border-subtle bg-bg-tertiary",
        size === "sm" ? "h-11 w-11 p-1.5" : "h-14 w-14 p-2"
      )}
    >
      <Image src={brand.logo} alt={`${brand.name} logo`} width={56} height={56} unoptimized className="h-full w-full object-contain" />
    </span>
  );
}

function SetupNotice({ error, message }: { error: string | null; message: string | null }) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={cn(
        "rounded-xl border px-4 py-3 text-sm",
        error ? "border-danger/30 bg-danger/10 text-danger" : "border-success/30 bg-success/10 text-success"
      )}
    >
      <div className="flex items-center gap-2">
        {error ? <AlertCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
        <span>{error || message}</span>
      </div>
    </div>
  );
}

function SetupFooter({
  step,
  isSubmitting,
  canContinue,
  onBack,
  onContinue,
  editMode,
}: {
  step: number;
  isSubmitting: boolean;
  canContinue: boolean;
  onBack: () => void;
  onContinue: () => void;
  editMode: boolean;
}) {
  return (
    <footer className="sticky bottom-[72px] z-20 -mx-4 flex flex-row gap-3 border-t border-border-subtle bg-bg-primary/95 px-4 pb-3 pt-3 backdrop-blur-xl sm:static sm:mx-0 sm:items-center sm:justify-between sm:bg-transparent sm:px-0 sm:pb-0 sm:pt-5 sm:backdrop-blur-none">
      <Button type="button" variant="outline" onClick={onBack} disabled={isSubmitting} className="w-full sm:w-auto">
        <ArrowLeft className="h-4 w-4" />
        Back
      </Button>
      <Button
        type="button"
        variant="accent"
        onClick={onContinue}
        disabled={isSubmitting || (step === 1 && !canContinue)}
        className="w-full bg-accent-dark text-white hover:bg-accent sm:w-auto"
      >
        {isSubmitting && <IOSSpinner size={16} />}
        {!isSubmitting && step === 4 && <Check className="h-4 w-4" />}
        {isSubmitting
          ? "Testing connection"
          : step === 4
            ? editMode
              ? "Save & test connection"
              : "Connect account"
            : "Continue"}
        {!isSubmitting && step < 4 && <ArrowRight className="h-4 w-4" />}
      </Button>
    </footer>
  );
}
