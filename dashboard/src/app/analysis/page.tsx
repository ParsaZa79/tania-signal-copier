"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getAnalysisSummary, runAnalysis } from "@/lib/api";
import {
  BarChart3,
  Download,
  FileText,
  RefreshCw,
  Loader2,
  Target,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Clock,
  Lightbulb,
  Zap,
  Calendar,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

interface AnalysisSummaryData {
  total_signals: number;
  tp2_hit: number;
  tp1_hit: number;
  sl_hit: number;
  tp_unnumbered: number;
  win_rate: number;
  tp1_to_tp2_conversion: number;
  date_range: { start: string; end: string } | null;
  avg_time_to_tp1_minutes?: number;
  avg_time_to_tp2_minutes?: number;
}

export default function AnalysisPage() {
  const [summary, setSummary] = useState<AnalysisSummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [output, setOutput] = useState<string>("");

  // Analysis parameters
  const [total, setTotal] = useState("1000");
  const [batch, setBatch] = useState("100");
  const [delay, setDelay] = useState("2");

  const loadSummary = useCallback(async () => {
    try {
      const res = await getAnalysisSummary();
      if (res.success) {
        setSummary(res.summary);
      }
    } catch (error) {
      console.error("Failed to load analysis:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const handleFetch = async () => {
    setIsFetching(true);
    setOutput("");

    try {
      const res = await runAnalysis("fetch", {
        total: parseInt(total, 10),
        batch: parseInt(batch, 10),
        delay: parseFloat(delay),
      });

      if (res.success) {
        setOutput(res.output || "Fetch completed successfully");
        await loadSummary();
      } else {
        setOutput(`Error: ${res.error}`);
      }
    } catch (error) {
      setOutput(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsFetching(false);
    }
  };

  const handleReport = async () => {
    setIsGenerating(true);
    setOutput("");

    try {
      const res = await runAnalysis("report");

      if (res.success) {
        setOutput(res.output || "Report generated successfully");
        await loadSummary();
      } else {
        setOutput(`Error: ${res.error}`);
      }
    } catch (error) {
      setOutput(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleFetchAndReport = async () => {
    await handleFetch();
    if (!output.startsWith("Error:")) {
      await handleReport();
    }
  };

  const formatMinutes = (minutes?: number) => {
    if (!minutes) return "-";
    if (minutes < 60) return `${minutes.toFixed(0)}m`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}h ${mins}m`;
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

  const isRunning = isFetching || isGenerating;

  return (
    <PageContainer>
      {/* Header */}
      <AnimatedSection>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-text-primary tracking-tight">Signal Analysis</h1>
            <p className="text-sm text-text-muted mt-1">Fetch messages and analyze signal outcomes</p>
          </div>

          <Button variant="ghost" size="icon" onClick={loadSummary}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </AnimatedSection>

      {/* Controls */}
      <AnimatedSection>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
                <Download className="w-5 h-5 text-accent" />
              </div>
              <span>Fetch & Analyze</span>
            </CardTitle>
          </CardHeader>

          <CardContent className="p-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="w-24">
                <Input
                  label="Messages"
                  value={total}
                  onChange={(e) => setTotal(e.target.value)}
                  type="number"
                  min="1"
                />
              </div>
              <div className="w-24">
                <Input
                  label="Batch Size"
                  value={batch}
                  onChange={(e) => setBatch(e.target.value)}
                  type="number"
                  min="1"
                />
              </div>
              <div className="w-20">
                <Input
                  label="Delay (s)"
                  value={delay}
                  onChange={(e) => setDelay(e.target.value)}
                  type="number"
                  min="0"
                  step="0.5"
                />
              </div>

              <div className="flex gap-3 ml-auto">
                <Button
                  variant="secondary"
                  onClick={handleFetch}
                  disabled={isRunning}
                >
                  {isFetching ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  Fetch
                </Button>

                <Button
                  variant="secondary"
                  onClick={handleReport}
                  disabled={isRunning}
                >
                  {isGenerating ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <FileText className="w-4 h-4 mr-2" />
                  )}
                  Report
                </Button>

                <Button
                  variant="accent"
                  onClick={handleFetchAndReport}
                  disabled={isRunning}
                >
                  {isRunning ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Zap className="w-4 h-4 mr-2" />
                  )}
                  Fetch + Report
                </Button>
              </div>
            </div>

            {/* Output */}
            {output && (
              <div className="mt-4 p-4 rounded-xl bg-bg-primary border border-border-subtle font-mono text-xs max-h-48 overflow-y-auto whitespace-pre-wrap">
                {output}
              </div>
            )}
          </CardContent>
        </Card>
      </AnimatedSection>

      {/* Summary Header */}
      <AnimatedSection>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-accent" />
            Outcome Summary
          </h2>
          {summary?.date_range && (
            <Badge variant="default" className="bg-bg-tertiary">
              <Calendar className="w-3 h-3 mr-1" />
              {summary.date_range.start} to {summary.date_range.end}
            </Badge>
          )}
        </div>
      </AnimatedSection>

      {/* Metrics Grid */}
      {summary && summary.total_signals > 0 ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <AnimatedSection className="stagger-1">
              <MetricCard
                label="Total Signals"
                value={summary.total_signals.toString()}
                icon={<BarChart3 className="w-5 h-5" />}
                color="accent"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-2">
              <MetricCard
                label="Win Rate"
                value={`${summary.win_rate.toFixed(1)}%`}
                icon={<TrendingUp className="w-5 h-5" />}
                color="success"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-3">
              <MetricCard
                label="TP2 Hit"
                value={summary.tp2_hit.toString()}
                icon={<Target className="w-5 h-5" />}
                color="success"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-4">
              <MetricCard
                label="TP1 Hit"
                value={summary.tp1_hit.toString()}
                icon={<Target className="w-5 h-5" />}
                color="info"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-5">
              <MetricCard
                label="SL Hit"
                value={summary.sl_hit.toString()}
                icon={<TrendingDown className="w-5 h-5" />}
                color="danger"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-5">
              <MetricCard
                label="TP1→TP2"
                value={`${summary.tp1_to_tp2_conversion.toFixed(1)}%`}
                icon={<ArrowRight className="w-5 h-5" />}
                color="warning"
              />
            </AnimatedSection>
          </div>

          {/* Time Metrics */}
          {(summary.avg_time_to_tp1_minutes || summary.avg_time_to_tp2_minutes) && (
            <AnimatedSection>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-info/20 flex items-center justify-center">
                      <Clock className="w-5 h-5 text-info" />
                    </div>
                    <span>Average Time to Target</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
                      <p className="text-xs uppercase tracking-wide text-text-muted mb-1">Time to TP1</p>
                      <p className="text-2xl font-bold text-info tabular-nums">
                        {formatMinutes(summary.avg_time_to_tp1_minutes)}
                      </p>
                    </div>
                    <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
                      <p className="text-xs uppercase tracking-wide text-text-muted mb-1">Time to TP2</p>
                      <p className="text-2xl font-bold text-success tabular-nums">
                        {formatMinutes(summary.avg_time_to_tp2_minutes)}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </AnimatedSection>
          )}
        </>
      ) : (
        <AnimatedSection>
          <div className="p-12 text-center rounded-xl bg-bg-tertiary/30 border border-border-subtle">
            <BarChart3 className="w-16 h-16 mx-auto mb-4 text-text-muted opacity-30" />
            <h3 className="text-lg font-medium text-text-secondary mb-2">No Analysis Data</h3>
            <p className="text-sm text-text-muted mb-6">
              Run &quot;Fetch + Report&quot; to analyze signal outcomes from your Telegram channel.
            </p>
            <Button variant="accent" onClick={handleFetchAndReport} disabled={isRunning}>
              {isRunning ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Zap className="w-4 h-4 mr-2" />
              )}
              Generate Analysis
            </Button>
          </div>
        </AnimatedSection>
      )}

      {/* Insights */}
      <AnimatedSection>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-warning/20 flex items-center justify-center">
                <Lightbulb className="w-5 h-5 text-warning" />
              </div>
              <span>Insights</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
              <InsightItem text="TP1→TP2 conversion rate shows how well runners perform after scalp exits" />
              <InsightItem text="If TP1-only dominates, consider earlier partial exits or tighter TP2" />
              <InsightItem text="Average time-to-TP helps optimize session timing and trade management" />
              <InsightItem text="High SL rate may indicate need for better entry timing or wider stops" />
            </div>
          </CardContent>
        </Card>
      </AnimatedSection>
    </PageContainer>
  );
}

function MetricCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: "accent" | "success" | "danger" | "warning" | "info";
}) {
  const colorStyles = {
    accent: { bg: "bg-accent/10", border: "border-accent/30", text: "text-accent" },
    success: { bg: "bg-success/10", border: "border-success/30", text: "text-success" },
    danger: { bg: "bg-danger/10", border: "border-danger/30", text: "text-danger" },
    warning: { bg: "bg-warning/10", border: "border-warning/30", text: "text-warning" },
    info: { bg: "bg-info/10", border: "border-info/30", text: "text-info" },
  };

  const styles = colorStyles[color];

  return (
    <div className={`p-4 rounded-xl ${styles.bg} border ${styles.border}`}>
      <div className={`flex items-center gap-2 ${styles.text} mb-2`}>
        {icon}
      </div>
      <p className={`text-2xl font-bold tabular-nums ${styles.text}`}>{value}</p>
      <p className="text-xs text-text-muted mt-1">{label}</p>
    </div>
  );
}

function InsightItem({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-bg-tertiary/30 border border-border-subtle">
      <div className="w-2 h-2 rounded-full bg-info mt-1.5 flex-shrink-0" />
      <p className="text-sm text-text-secondary">{text}</p>
    </div>
  );
}
