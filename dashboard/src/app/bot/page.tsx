"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  getBotStatus,
  startBot,
  stopBot,
  getBotConfig,
  getTrackedPositions,
  clearTrackedPositions,
} from "@/lib/api";
import { API_URL } from "@/lib/constants";
import {
  Play,
  Square,
  Bot,
  RefreshCw,
  Trash2,
  Loader2,
  Clock,
  Zap,
  FileText,
  Server,
  Activity,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";
import type { TrackedPosition } from "@/types";

const IS_MACOS = typeof window !== "undefined" && navigator.platform.includes("Mac");

type BotStatusType = "stopped" | "starting" | "running" | "stopping" | "error";

export default function BotControlPage() {
  const [status, setStatus] = useState<BotStatusType>("stopped");
  const [pid, setPid] = useState<number | undefined>();
  const [startedAt, setStartedAt] = useState<string | undefined>();
  const [error, setError] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  // Options
  const [writeEnvOnStart, setWriteEnvOnStart] = useState(false);
  const [preventSleep, setPreventSleep] = useState(IS_MACOS);

  // Positions
  const [positions, setPositions] = useState<TrackedPosition[]>([]);
  const [positionsStats, setPositionsStats] = useState({ total: 0, open: 0, closed: 0 });

  // Log output
  const [logs, setLogs] = useState<Array<{ id: string; level: string; message: string; timestamp: string }>>([]);
  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getBotStatus();
      if (res.success) {
        setStatus(res.status);
        setPid(res.pid);
        setStartedAt(res.started_at);
        setError(res.error);
      }
    } catch (err) {
      console.error("Failed to fetch bot status:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchPositions = useCallback(async () => {
    try {
      const res = await getTrackedPositions();
      if (res.success) {
        setPositions(res.positions as TrackedPosition[]);
        setPositionsStats({ total: res.total, open: res.open, closed: res.closed });
      }
    } catch (err) {
      console.error("Failed to fetch positions:", err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchPositions();

    // Poll status every 3 seconds
    const interval = setInterval(() => {
      fetchStatus();
      fetchPositions();
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchStatus, fetchPositions]);

  // WebSocket connection for log streaming
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, "ws") + "/ws/logs";
    let reconnectTimeout: NodeJS.Timeout;
    let ws: WebSocket | null = null;
    let isCleaningUp = false;

    const connect = () => {
      if (isCleaningUp) return;

      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isCleaningUp) {
            ws?.close();
            return;
          }
          console.log("Log WebSocket connected");
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          if (isCleaningUp) return;
          try {
            const data = JSON.parse(event.data);

            if (data.type === "history" && Array.isArray(data.logs)) {
              // Received buffered log history
              setLogs(data.logs.slice(-100));
            } else if (data.type === "log" && data.log) {
              // Single new log entry
              setLogs((prev) => [...prev.slice(-99), data.log]);
            }
          } catch (err) {
            console.error("Failed to parse log message:", err);
          }
        };

        ws.onclose = () => {
          if (isCleaningUp) return;
          console.log("Log WebSocket disconnected");
          setWsConnected(false);
          wsRef.current = null;

          // Reconnect after 3 seconds
          reconnectTimeout = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
          // WebSocket errors are expected during cleanup or reconnection
          // The onclose handler will handle reconnection
          if (!isCleaningUp && ws) {
            ws.close();
          }
        };
      } catch (err) {
        console.error("Failed to create WebSocket:", err);
        // Retry connection after delay
        if (!isCleaningUp) {
          reconnectTimeout = setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return () => {
      isCleaningUp = true;
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleStart = async () => {
    setIsStarting(true);
    setError(undefined);

    try {
      let config: Record<string, string> | undefined;
      if (writeEnvOnStart) {
        const configRes = await getBotConfig();
        if (configRes.success) {
          config = configRes.config;
        }
      }

      const res = await startBot({
        preventSleep,
        writeEnv: writeEnvOnStart,
        config,
      });

      if (res.success) {
        setStatus("starting");
        addLog("info", `Bot starting${res.pid ? ` (PID: ${res.pid})` : ""}...`);
      } else {
        setError(res.error);
        addLog("error", `Failed to start: ${res.error}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      addLog("error", `Failed to start: ${message}`);
    } finally {
      setIsStarting(false);
      fetchStatus();
    }
  };

  const handleStop = async () => {
    setIsStopping(true);

    try {
      const res = await stopBot();

      if (res.success) {
        setStatus("stopping");
        addLog("info", "Bot stopping...");
      } else {
        setError(res.error);
        addLog("error", `Failed to stop: ${res.error}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      addLog("error", `Failed to stop: ${message}`);
    } finally {
      setIsStopping(false);
      fetchStatus();
    }
  };

  const handleClearPositions = async () => {
    if (!confirm("Are you sure you want to clear all tracked positions?")) return;

    try {
      await clearTrackedPositions();
      setPositions([]);
      setPositionsStats({ total: 0, open: 0, closed: 0 });
      addLog("info", "Cleared all tracked positions");
    } catch (err) {
      console.error("Failed to clear positions:", err);
    }
  };

  const addLog = (level: string, message: string) => {
    setLogs((prev) => [
      ...prev.slice(-99), // Keep last 100 logs
      {
        id: `${Date.now()}-${Math.random()}`,
        level,
        message,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
  };

  const getStatusColor = (s: BotStatusType) => {
    switch (s) {
      case "running":
        return "success";
      case "starting":
      case "stopping":
        return "warning";
      case "error":
        return "danger";
      default:
        return "default";
    }
  };

  const getStatusIcon = (s: BotStatusType) => {
    switch (s) {
      case "running":
        return <Activity className="w-5 h-5 text-success animate-pulse" />;
      case "starting":
      case "stopping":
        return <Loader2 className="w-5 h-5 text-warning animate-spin" />;
      case "error":
        return <AlertCircle className="w-5 h-5 text-danger" />;
      default:
        return <Square className="w-5 h-5 text-text-muted" />;
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {/* Header */}
      <AnimatedSection>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-text-primary tracking-tight">Bot Control</h1>
            <p className="text-sm text-text-muted mt-1">Start, stop, and monitor the signal copier bot</p>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={fetchStatus}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </AnimatedSection>

      {/* Main Control Card */}
      <AnimatedSection>
        <Card className="overflow-hidden">
          <CardHeader className="bg-gradient-to-r from-accent/15 to-transparent">
            <CardTitle className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center">
                <Bot className="w-6 h-6 text-accent" />
              </div>
              <div>
                <span>Signal Copier Bot</span>
                <div className="flex items-center gap-2 mt-1">
                  {getStatusIcon(status)}
                  <Badge variant={getStatusColor(status)} className="capitalize">
                    {status}
                  </Badge>
                  {pid && (
                    <span className="text-xs text-text-muted">PID: {pid}</span>
                  )}
                </div>
              </div>
            </CardTitle>
          </CardHeader>

          <CardContent className="p-6">
            {/* Error Display */}
            {error && (
              <div className="mb-6 p-4 rounded-xl bg-danger/10 border border-danger/30 text-danger text-sm">
                {error}
              </div>
            )}

            {/* Control Buttons */}
            <div className="flex items-center gap-4 mb-6">
              <Button
                variant="accent"
                size="lg"
                onClick={handleStart}
                disabled={isStarting || status === "running" || status === "starting"}
                className="min-w-[140px]"
              >
                {isStarting ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Play className="w-5 h-5 mr-2" />
                )}
                Start Bot
              </Button>

              <Button
                variant="danger"
                size="lg"
                onClick={handleStop}
                disabled={isStopping || status === "stopped" || status === "stopping"}
                className="min-w-[140px]"
              >
                {isStopping ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Square className="w-5 h-5 mr-2" />
                )}
                Stop Bot
              </Button>
            </div>

            {/* Options */}
            <div className="flex flex-wrap items-center gap-6 p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
              <Checkbox
                label="Write .env on start"
                checked={writeEnvOnStart}
                onChange={(e) => setWriteEnvOnStart(e.target.checked)}
              />

              <Checkbox
                label={IS_MACOS ? "Prevent sleep (caffeinate)" : "Prevent sleep (macOS only)"}
                checked={preventSleep}
                onChange={(e) => setPreventSleep(e.target.checked)}
                disabled={!IS_MACOS}
              />
            </div>

            {/* Status Info */}
            {status === "running" && startedAt && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                <StatusCard icon={<Clock className="w-5 h-5" />} label="Started" value={new Date(startedAt).toLocaleString()} />
                <StatusCard icon={<Server className="w-5 h-5" />} label="Process ID" value={String(pid || "-")} />
                <StatusCard icon={<CheckCircle className="w-5 h-5" />} label="Status" value="Healthy" color="success" />
              </div>
            )}
          </CardContent>
        </Card>
      </AnimatedSection>

      {/* Tracked Positions */}
      <AnimatedSection>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-info/20 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-info" />
                </div>
                <span>Tracked Positions</span>
                <Badge variant="default">{positionsStats.total}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={fetchPositions}>
                  <RefreshCw className="w-4 h-4" />
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleClearPositions}
                  disabled={positions.length === 0}
                >
                  <Trash2 className="w-4 h-4 mr-1" />
                  Clear
                </Button>
              </div>
            </CardTitle>
          </CardHeader>

          <CardContent className="p-0">
            {positions.length === 0 ? (
              <div className="p-8 text-center text-text-muted">
                <Activity className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No tracked positions</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full data-table">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="px-4 py-3 text-left">Msg ID</th>
                      <th className="px-4 py-3 text-left">Ticket</th>
                      <th className="px-4 py-3 text-left">Symbol</th>
                      <th className="px-4 py-3 text-left">Role</th>
                      <th className="px-4 py-3 text-left">Type</th>
                      <th className="px-4 py-3 text-right">Entry</th>
                      <th className="px-4 py-3 text-right">SL</th>
                      <th className="px-4 py-3 text-right">Lot</th>
                      <th className="px-4 py-3 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.slice(0, 10).map((pos, idx) => (
                      <tr key={`${pos.msg_id}-${pos.role}-${idx}`} className="border-b border-border-subtle">
                        <td className="px-4 py-3 text-text-secondary tabular-nums">{pos.msg_id}</td>
                        <td className="px-4 py-3 text-text-primary tabular-nums">{pos.mt5_ticket || "-"}</td>
                        <td className="px-4 py-3 font-medium text-text-primary">{pos.symbol}</td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={pos.role === "scalp" ? "default" : pos.role === "runner" ? "warning" : "default"}
                            className="capitalize"
                          >
                            {pos.role}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 uppercase text-text-secondary">{pos.order_type}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-text-primary">
                          {pos.entry_price?.toFixed(5) || "-"}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-danger">
                          {pos.stop_loss?.toFixed(5) || "-"}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-text-secondary">
                          {pos.lot_size?.toFixed(2) || "-"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={pos.status === "open" ? "success" : pos.status === "closed" ? "default" : "warning"}
                            className="capitalize"
                          >
                            {pos.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {positions.length > 10 && (
                  <div className="p-3 text-center text-sm text-text-muted border-t border-border-subtle">
                    Showing 10 of {positions.length} positions
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </AnimatedSection>

      {/* Log Output */}
      <AnimatedSection>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-warning/20 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-warning" />
                </div>
                <span>Output Log</span>
                {wsConnected && (
                  <Badge variant="success" className="text-xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-success mr-1.5 animate-pulse" />
                    Live
                  </Badge>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setLogs([]);
                  // Also clear server-side buffer
                  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send("clear");
                  }
                }}
              >
                Clear
              </Button>
            </CardTitle>
          </CardHeader>

          <CardContent className="p-0">
            <div className="h-64 overflow-y-auto p-4 bg-bg-primary font-mono text-xs">
              {logs.length === 0 ? (
                <div className="text-text-muted text-center py-8">
                  {wsConnected ? "Waiting for bot output..." : "Connecting to log stream..."}
                </div>
              ) : (
                logs.map((log) => {
                  // Format timestamp - handle both ISO format and local time string
                  const time = log.timestamp.includes("T")
                    ? new Date(log.timestamp).toLocaleTimeString()
                    : log.timestamp;

                  return (
                    <div
                      key={log.id}
                      className={`py-1 ${
                        log.level === "error"
                          ? "text-danger"
                          : log.level === "warning"
                            ? "text-warning"
                            : "text-text-secondary"
                      }`}
                    >
                      <span className="text-text-muted">[{time}]</span> {log.message}
                    </div>
                  );
                })
              )}
              <div ref={logEndRef} />
            </div>
          </CardContent>
        </Card>
      </AnimatedSection>

      {/* Tips */}
      <AnimatedSection>
        <div className="flex items-center gap-3 p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
          <Zap className="w-5 h-5 text-accent flex-shrink-0" />
          <p className="text-sm text-text-muted">
            <span className="font-medium text-text-secondary">Tip:</span> The bot will automatically reconnect
            if the connection is lost. Check the Configuration page to update your settings.
          </p>
        </div>
      </AnimatedSection>
    </PageContainer>
  );
}

function StatusCard({
  icon,
  label,
  value,
  color = "default",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color?: "default" | "success" | "danger" | "warning";
}) {
  const colorStyles = {
    default: "text-text-primary",
    success: "text-success",
    danger: "text-danger",
    warning: "text-warning",
  };

  return (
    <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
      <div className="flex items-center gap-2 text-text-muted mb-1">
        {icon}
        <span className="text-xs uppercase tracking-wide">{label}</span>
      </div>
      <p className={`text-lg font-semibold ${colorStyles[color]}`}>{value}</p>
    </div>
  );
}
