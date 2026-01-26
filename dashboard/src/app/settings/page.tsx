"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getHealth } from "@/lib/api";
import type { HealthStatus } from "@/types";
import {
  Server,
  Wifi,
  Shield,
  CheckCircle,
  XCircle,
  Zap,
  Activity,
  DollarSign,
  Sparkles,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchHealth = async () => {
    try {
      const result = await getHealth();
      setHealth(result);
    } catch (error) {
      console.error("Failed to fetch health:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <PageContainer>
      {/* Page Header */}
      <AnimatedSection>
        <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
          Settings
        </h1>
        <p className="text-sm text-text-muted mt-1">
          System configuration and status
        </p>
      </AnimatedSection>

      {/* Connection Status */}
      <AnimatedSection>
        <Card>
        <CardHeader className="bg-gradient-to-r from-accent/10 to-transparent">
          <CardTitle className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
              <Server className="w-5 h-5 text-accent" />
            </div>
            <span>Connection Status</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          {isLoading ? (
            <div className="flex items-center gap-3 text-text-muted">
              <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <span>Checking connection status...</span>
            </div>
          ) : !health ? (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-danger/10 border border-danger/20">
              <XCircle className="w-5 h-5 text-danger" />
              <span className="text-danger">
                Unable to connect to API server
              </span>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Overall Status */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-success/15 to-success/5 border border-success/30">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-success/20 flex items-center justify-center">
                    <Wifi className="w-6 h-6 text-success" />
                  </div>
                  <div>
                    <span className="font-medium text-text-primary">
                      API Server
                    </span>
                    <p className="text-xs text-text-muted">
                      Main connection
                    </p>
                  </div>
                </div>
                <Badge variant="success" className="px-4 py-1.5 text-sm">
                  {health.status.toUpperCase()}
                </Badge>
              </div>

              {/* MT5 Connection Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <StatusCard
                  icon={<Activity className="w-5 h-5" />}
                  label="MT5 Connected"
                  status={health.mt5.connected}
                  color="info"
                />

                {health.mt5.ping_ok !== undefined && (
                  <StatusCard
                    icon={<Zap className="w-5 h-5" />}
                    label="Ping OK"
                    status={health.mt5.ping_ok}
                    color="warning"
                  />
                )}

                {health.mt5.account_accessible !== undefined && (
                  <StatusCard
                    icon={<Shield className="w-5 h-5" />}
                    label="Account Accessible"
                    status={health.mt5.account_accessible}
                    color="accent"
                  />
                )}

                {health.mt5.trading_enabled !== undefined && (
                  <StatusCard
                    icon={<CheckCircle className="w-5 h-5" />}
                    label="Trading Enabled"
                    status={health.mt5.trading_enabled}
                    color="success"
                  />
                )}
              </div>

              {health.mt5.account_balance !== undefined && (
                <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-accent/20 to-accent/5 border border-accent/40">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center">
                      <DollarSign className="w-6 h-6 text-bg-primary" />
                    </div>
                    <span className="text-text-secondary font-medium">
                      Account Balance
                    </span>
                  </div>
                  <span className="text-2xl font-bold text-accent tabular-nums">
                    ${health.mt5.account_balance.toFixed(2)}
                  </span>
                </div>
              )}

              {health.mt5.error && (
                <div className="p-4 rounded-xl bg-danger/10 border border-danger/20">
                  <p className="font-medium text-danger mb-1">Error</p>
                  <p className="text-sm text-danger/80">
                    {health.mt5.error}
                  </p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      </AnimatedSection>

      {/* About */}
      <AnimatedSection>
        <Card>
        <CardHeader className="bg-gradient-to-r from-info/10 to-transparent">
          <CardTitle className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-info/20 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-info" />
            </div>
            <span>About</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <VersionCard label="Dashboard" version="0.1.0" color="accent" />
            <VersionCard label="API" version="0.1.0" color="success" />
            <VersionCard label="Next.js" version="16.1.1" color="info" />
            <VersionCard label="React" version="19.2.3" color="warning" />
          </div>
        </CardContent>
      </Card>
      </AnimatedSection>
    </PageContainer>
  );
}

function StatusCard({
  icon,
  label,
  status,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  status: boolean;
  color: "success" | "info" | "warning" | "accent";
}) {
  const styles = {
    success: "bg-success/10 border-success/30 text-success",
    info: "bg-info/10 border-info/30 text-info",
    warning: "bg-warning/10 border-warning/30 text-warning",
    accent: "bg-accent/10 border-accent/30 text-accent",
  };

  return (
    <div className={`flex items-center justify-between p-4 rounded-xl border ${styles[color]}`}>
      <div className="flex items-center gap-3">
        <span>{icon}</span>
        <span className="text-sm text-text-primary font-medium">{label}</span>
      </div>
      {status ? (
        <CheckCircle className="w-5 h-5 text-success" />
      ) : (
        <XCircle className="w-5 h-5 text-danger" />
      )}
    </div>
  );
}

function VersionCard({
  label,
  version,
  color,
}: {
  label: string;
  version: string;
  color: "success" | "info" | "warning" | "accent";
}) {
  const styles = {
    success: "from-success/15 to-success/5 border-success/30",
    info: "from-info/15 to-info/5 border-info/30",
    warning: "from-warning/15 to-warning/5 border-warning/30",
    accent: "from-accent/15 to-accent/5 border-accent/30",
  };

  const textStyles = {
    success: "text-success",
    info: "text-info",
    warning: "text-warning",
    accent: "text-accent",
  };

  return (
    <div className={`p-4 rounded-xl bg-gradient-to-br ${styles[color]} border text-center`}>
      <p className="text-[10px] uppercase tracking-wide text-text-muted mb-1">
        {label}
      </p>
      <p className={`text-lg font-bold tabular-nums ${textStyles[color]}`}>
        v{version}
      </p>
    </div>
  );
}
