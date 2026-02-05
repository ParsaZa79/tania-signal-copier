"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  getBotConfig,
  saveBotConfig,
  getPresets,
  getPreset,
  savePreset,
  deletePreset,
  getTelegramChannels,
  type TelegramChannel,
} from "@/lib/api";
import {
  Send,
  Server,
  TrendingUp,
  Settings2,
  Save,
  Trash2,
  Plus,
  ChevronDown,
  Loader2,
  Check,
  AlertCircle,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ChannelSelector } from "@/components/ui/channel-selector";

const IS_MACOS = typeof window !== "undefined" && navigator.platform.includes("Mac");

interface ConfigSection {
  title: string;
  icon: React.ReactNode;
  color: string;
  fields: Array<{
    key: string;
    label: string;
    type: "text" | "password" | "select" | "channel";
    placeholder?: string;
    options?: Array<{ value: string; label: string }>;
    condition?: () => boolean;
  }>;
}

export default function ConfigPage() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [presets, setPresets] = useState<Array<{ name: string; created_at: string; modified_at: string }>>([]);
  const [currentPreset, setCurrentPreset] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [showPresetDialog, setShowPresetDialog] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [presetDropdownOpen, setPresetDropdownOpen] = useState(false);

  // Telegram channels state
  const [channels, setChannels] = useState<TelegramChannel[]>([]);
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);
  const [channelsError, setChannelsError] = useState<string | null>(null);

  const configSections: ConfigSection[] = [
    {
      title: "Telegram",
      icon: <Send className="w-5 h-5" />,
      color: "info",
      fields: [
        { key: "TELEGRAM_API_ID", label: "API ID", type: "text", placeholder: "123456789" },
        { key: "TELEGRAM_API_HASH", label: "API Hash", type: "password", placeholder: "Your API hash" },
        { key: "TELEGRAM_CHANNEL", label: "Channel", type: "channel", placeholder: "Channel name or ID" },
      ],
    },
    {
      title: "MetaTrader 5",
      icon: <Server className="w-5 h-5" />,
      color: "success",
      fields: [
        { key: "MT5_LOGIN", label: "Login", type: "text", placeholder: "Account number" },
        { key: "MT5_PASSWORD", label: "Password", type: "password", placeholder: "Your password" },
        { key: "MT5_SERVER", label: "Server", type: "text", placeholder: "Broker-Server" },
        ...(IS_MACOS
          ? [
              { key: "MT5_DOCKER_HOST", label: "Docker Host", type: "text" as const, placeholder: "localhost" },
              { key: "MT5_DOCKER_PORT", label: "Docker Port", type: "text" as const, placeholder: "18812" },
            ]
          : [{ key: "MT5_PATH", label: "MT5 Path (optional)", type: "text" as const, placeholder: "Auto-detected" }]),
      ],
    },
    {
      title: "Trading",
      icon: <TrendingUp className="w-5 h-5" />,
      color: "accent",
      fields: [
        { key: "DEFAULT_LOT_SIZE", label: "Default Lot Size", type: "text", placeholder: "0.01" },
        { key: "MAX_RISK_PERCENT", label: "Max Risk %", type: "text", placeholder: "2" },
        { key: "SCALP_LOT_SIZE", label: "Scalp Lot Size", type: "text", placeholder: "0.01" },
        { key: "RUNNER_LOT_SIZE", label: "Runner Lot Size", type: "text", placeholder: "0.01" },
        {
          key: "TRADING_STRATEGY",
          label: "Strategy",
          type: "select",
          options: [
            { value: "dual_tp", label: "Dual TP (Scalp + Runner)" },
            { value: "single", label: "Single Position" },
          ],
        },
        { key: "EDIT_WINDOW_SECONDS", label: "Edit Window (sec)", type: "text", placeholder: "120" },
      ],
    },
    {
      title: "Optional",
      icon: <Settings2 className="w-5 h-5" />,
      color: "muted",
      fields: [{ key: "TEST_SYMBOL", label: "Test Symbol", type: "text", placeholder: "EURUSD" }],
    },
  ];

  const loadData = useCallback(async () => {
    try {
      const [configRes, presetsRes] = await Promise.all([getBotConfig(), getPresets()]);

      if (configRes.success) {
        setConfig(configRes.config);
      }

      if (presetsRes.success) {
        setPresets(presetsRes.presets);
        if (presetsRes.lastPreset) {
          setCurrentPreset(presetsRes.lastPreset);
        }
      }
    } catch (error) {
      console.error("Failed to load config:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefreshChannels = useCallback(async () => {
    const apiId = config.TELEGRAM_API_ID;
    const apiHash = config.TELEGRAM_API_HASH;

    if (!apiId || !apiHash) {
      setChannelsError("Please enter API ID and API Hash first");
      return;
    }

    setIsLoadingChannels(true);
    setChannelsError(null);

    try {
      const res = await getTelegramChannels(apiId, apiHash);
      setChannels(res.channels);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch channels";
      setChannelsError(message);
    } finally {
      setIsLoadingChannels(false);
    }
  }, [config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH]);

  const handleFieldChange = (key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaveStatus("idle");
  };

  const handleSave = async (writeEnv = false) => {
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      await saveBotConfig(config, writeEnv);

      if (currentPreset) {
        await savePreset(currentPreset, config);
      }

      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch (error) {
      console.error("Failed to save:", error);
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadPreset = async (name: string) => {
    try {
      const res = await getPreset(name);
      if (res.success) {
        setConfig(res.preset.values);
        setCurrentPreset(name);
      }
    } catch (error) {
      console.error("Failed to load preset:", error);
    }
    setPresetDropdownOpen(false);
  };

  const handleSaveAsPreset = async () => {
    if (!newPresetName.trim()) return;

    try {
      await savePreset(newPresetName.trim(), config);
      setCurrentPreset(newPresetName.trim());
      setNewPresetName("");
      setShowPresetDialog(false);

      // Refresh presets list
      const presetsRes = await getPresets();
      if (presetsRes.success) {
        setPresets(presetsRes.presets);
      }
    } catch (error) {
      console.error("Failed to save preset:", error);
    }
  };

  const handleDeletePreset = async () => {
    if (!currentPreset) return;

    try {
      await deletePreset(currentPreset);
      setCurrentPreset(null);

      // Refresh presets list
      const presetsRes = await getPresets();
      if (presetsRes.success) {
        setPresets(presetsRes.presets);
      }
    } catch (error) {
      console.error("Failed to delete preset:", error);
    }
  };

  const colorStyles: Record<string, { bg: string; border: string; text: string }> = {
    info: { bg: "bg-info/10", border: "border-info/30", text: "text-info" },
    success: { bg: "bg-success/10", border: "border-success/30", text: "text-success" },
    accent: { bg: "bg-accent/10", border: "border-accent/30", text: "text-accent" },
    muted: { bg: "bg-bg-tertiary", border: "border-border-subtle", text: "text-text-muted" },
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
            <h1 className="text-2xl font-semibold text-text-primary tracking-tight">Configuration</h1>
            <p className="text-sm text-text-muted mt-1">Bot settings and environment variables</p>
          </div>

          <div className="flex items-center gap-3">
            {/* Preset Selector */}
            <div className="relative">
              <button
                onClick={() => setPresetDropdownOpen(!presetDropdownOpen)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-bg-tertiary border border-border-subtle hover:border-accent/30 transition-colors"
              >
                <span className="text-sm text-text-secondary">
                  {currentPreset || "No preset"}
                </span>
                <ChevronDown className="w-4 h-4 text-text-muted" />
              </button>

              {presetDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setPresetDropdownOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-2 w-56 p-2 rounded-xl bg-bg-elevated border border-border-subtle shadow-lg z-20">
                    {presets.length === 0 ? (
                      <p className="px-3 py-2 text-sm text-text-muted">No presets saved</p>
                    ) : (
                      presets.map((preset) => (
                        <button
                          key={preset.name}
                          onClick={() => handleLoadPreset(preset.name)}
                          className={`w-full px-3 py-2 text-left text-sm rounded-lg transition-colors ${
                            currentPreset === preset.name
                              ? "bg-accent/20 text-accent"
                              : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                          }`}
                        >
                          {preset.name}
                        </button>
                      ))
                    )}
                    <div className="border-t border-border-subtle mt-2 pt-2">
                      <button
                        onClick={() => {
                          setPresetDropdownOpen(false);
                          setShowPresetDialog(true);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-accent hover:bg-accent/10 rounded-lg transition-colors flex items-center gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        Save as new preset
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {currentPreset && (
              <Button variant="ghost" size="icon" onClick={handleDeletePreset}>
                <Trash2 className="w-4 h-4 text-danger" />
              </Button>
            )}

            {/* Save Buttons */}
            <Button variant="secondary" onClick={() => handleSave(false)} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : saveStatus === "success" ? (
                <Check className="w-4 h-4 text-success" />
              ) : saveStatus === "error" ? (
                <AlertCircle className="w-4 h-4 text-danger" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span className="ml-2">Save</span>
            </Button>

            <Button variant="accent" onClick={() => handleSave(true)} disabled={isSaving}>
              <Save className="w-4 h-4" />
              <span className="ml-2">Save to .env</span>
            </Button>
          </div>
        </div>
      </AnimatedSection>

      {/* Current Preset Badge */}
      {currentPreset && (
        <AnimatedSection>
          <Badge variant="default" className="bg-accent/20 text-accent border-accent/30">
            Active Preset: {currentPreset}
          </Badge>
        </AnimatedSection>
      )}

      {/* Config Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {configSections.map((section, idx) => {
          const colors = colorStyles[section.color];

          return (
            <AnimatedSection key={section.title} className={`stagger-${idx + 1}`}>
              <Card>
                <CardHeader className={`bg-gradient-to-r ${colors.bg} to-transparent`}>
                  <CardTitle className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center`}>
                      <span className={colors.text}>{section.icon}</span>
                    </div>
                    <span>{section.title}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-6">
                  <div className="space-y-4">
                    {section.fields.map((field) => {
                      if (field.condition && !field.condition()) return null;

                      if (field.type === "select") {
                        return (
                          <Select
                            key={field.key}
                            label={field.label}
                            value={config[field.key] || ""}
                            onChange={(e) => handleFieldChange(field.key, e.target.value)}
                            options={field.options || []}
                          />
                        );
                      }

                      if (field.type === "channel") {
                        // Parse comma-separated IDs to array
                        const selectedIds = (config[field.key] || "")
                          .split(",")
                          .map((id) => id.trim())
                          .filter(Boolean);

                        return (
                          <ChannelSelector
                            key={field.key}
                            channels={channels}
                            selectedChannelIds={selectedIds}
                            onSelectionChange={(channelIds) =>
                              handleFieldChange(field.key, channelIds.join(","))
                            }
                            onRefresh={handleRefreshChannels}
                            isLoading={isLoadingChannels}
                            error={channelsError}
                            disabled={!config.TELEGRAM_API_ID || !config.TELEGRAM_API_HASH}
                          />
                        );
                      }

                      return (
                        <Input
                          key={field.key}
                          label={field.label}
                          type={field.type}
                          value={config[field.key] || ""}
                          onChange={(e) => handleFieldChange(field.key, e.target.value)}
                          placeholder={field.placeholder}
                        />
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </AnimatedSection>
          );
        })}
      </div>

      {/* Save As Preset Dialog */}
      <Dialog open={showPresetDialog} onOpenChange={setShowPresetDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save as Preset</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <Input
              label="Preset Name"
              value={newPresetName}
              onChange={(e) => setNewPresetName(e.target.value)}
              placeholder="My Trading Setup"
              autoFocus
            />
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setShowPresetDialog(false)}>
                Cancel
              </Button>
              <Button variant="accent" onClick={handleSaveAsPreset} disabled={!newPresetName.trim()}>
                Save Preset
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
