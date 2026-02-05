"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  RefreshCw,
  Loader2,
  Check,
  Hash,
  Users,
  Radio,
  AlertCircle,
  Sparkles,
  X,
  ChevronDown,
} from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

export interface Channel {
  id: string;
  name: string;
  username?: string;
  type: "channel" | "group";
}

interface ChannelSelectorProps {
  channels: Channel[];
  selectedChannelIds: string[];
  onSelectionChange: (channelIds: string[]) => void;
  onRefresh: () => void;
  isLoading: boolean;
  error: string | null;
  disabled?: boolean;
}

export function ChannelSelector({
  channels,
  selectedChannelIds,
  onSelectionChange,
  onRefresh,
  isLoading,
  error,
  disabled = false,
}: ChannelSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isExpanded, setIsExpanded] = useState(false);

  const filteredChannels = useMemo(() => {
    if (!searchQuery.trim()) return channels;
    const query = searchQuery.toLowerCase();
    return channels.filter(
      (ch) =>
        ch.name.toLowerCase().includes(query) ||
        ch.username?.toLowerCase().includes(query) ||
        ch.id.includes(query)
    );
  }, [channels, searchQuery]);

  const selectedChannels = useMemo(
    () => channels.filter((ch) => selectedChannelIds.includes(ch.id)),
    [channels, selectedChannelIds]
  );

  const handleToggleChannel = (channelId: string) => {
    if (selectedChannelIds.includes(channelId)) {
      onSelectionChange(selectedChannelIds.filter((id) => id !== channelId));
    } else {
      onSelectionChange([...selectedChannelIds, channelId]);
    }
  };

  const handleRemoveChannel = (channelId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onSelectionChange(selectedChannelIds.filter((id) => id !== channelId));
  };

  const handleSelectAll = () => {
    onSelectionChange(filteredChannels.map((ch) => ch.id));
  };

  const handleClearAll = () => {
    onSelectionChange([]);
  };

  // Empty state - no channels loaded yet
  if (channels.length === 0 && !isLoading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-text-secondary">
            Signal Channels
          </label>
        </div>

        <div className="relative">
          <div className="p-6 rounded-2xl bg-gradient-to-br from-bg-tertiary/80 to-bg-tertiary/40 border border-border-subtle text-center">
            <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-info/10 flex items-center justify-center">
              <Radio className="w-6 h-6 text-info" />
            </div>
            <h4 className="text-sm font-medium text-text-primary mb-1">
              Load Your Channels
            </h4>
            <p className="text-xs text-text-muted mb-4">
              Enter your Telegram API credentials above, then fetch your channels
            </p>
            <Button
              variant="accent"
              size="sm"
              onClick={onRefresh}
              disabled={isLoading || disabled}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Fetch Channels
            </Button>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-3 p-3 rounded-xl bg-danger/10 border border-danger/30 flex items-start gap-2"
            >
              <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
              <p className="text-xs text-danger">{error}</p>
            </motion.div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-text-secondary">
          Signal Channels
          {selectedChannelIds.length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 text-xs rounded-md bg-accent/20 text-accent">
              {selectedChannelIds.length} selected
            </span>
          )}
        </label>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          disabled={isLoading || disabled}
          className="h-7 px-2 text-xs"
        >
          {isLoading ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <RefreshCw className="w-3 h-3" />
          )}
          <span className="ml-1.5">Refresh</span>
        </Button>
      </div>

      {/* Selected Channels Display / Trigger */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        disabled={disabled}
        className={cn(
          "w-full p-3 rounded-xl border text-left transition-all duration-200",
          "bg-bg-tertiary/50 hover:bg-bg-tertiary",
          isExpanded
            ? "border-accent/50 ring-2 ring-accent/20"
            : "border-border-subtle hover:border-border-default",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        {selectedChannels.length > 0 ? (
          <div className="space-y-2">
            {/* Selected channels chips */}
            <div className="flex flex-wrap gap-2">
              {selectedChannels.slice(0, 3).map((channel) => (
                <motion.div
                  key={channel.id}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={cn(
                    "flex items-center gap-2 px-2.5 py-1.5 rounded-lg",
                    "bg-bg-elevated border border-border-subtle",
                    "group"
                  )}
                >
                  <div
                    className={cn(
                      "w-5 h-5 rounded flex items-center justify-center",
                      channel.type === "channel"
                        ? "bg-info/15 text-info"
                        : "bg-success/15 text-success"
                    )}
                  >
                    {channel.type === "channel" ? (
                      <Radio className="w-3 h-3" />
                    ) : (
                      <Users className="w-3 h-3" />
                    )}
                  </div>
                  <span className="text-xs font-medium text-text-primary truncate max-w-[120px]">
                    {channel.name}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => handleRemoveChannel(channel.id, e)}
                    className="w-4 h-4 rounded-full bg-text-muted/20 hover:bg-danger/20 flex items-center justify-center transition-colors"
                  >
                    <X className="w-2.5 h-2.5 text-text-muted hover:text-danger" />
                  </button>
                </motion.div>
              ))}
              {selectedChannels.length > 3 && (
                <div className="flex items-center px-2.5 py-1.5 rounded-lg bg-accent/10 border border-accent/30">
                  <span className="text-xs font-medium text-accent">
                    +{selectedChannels.length - 3} more
                  </span>
                </div>
              )}
            </div>
            {/* Expand hint */}
            <div className="flex items-center justify-between text-xs text-text-muted">
              <span>Click to {isExpanded ? "collapse" : "manage channels"}</span>
              <ChevronDown
                className={cn(
                  "w-4 h-4 transition-transform",
                  isExpanded && "rotate-180"
                )}
              />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-text-muted">
              <div className="w-10 h-10 rounded-xl bg-bg-elevated flex items-center justify-center">
                <Hash className="w-5 h-5" />
              </div>
              <span className="text-sm">Select channels to listen to...</span>
            </div>
            <ChevronDown
              className={cn(
                "w-4 h-4 text-text-muted transition-transform",
                isExpanded && "rotate-180"
              )}
            />
          </div>
        )}
      </button>

      {/* Expanded Channel List */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-4 rounded-2xl bg-bg-secondary/50 border border-border-subtle space-y-3">
              {/* Search & Actions */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search channels..."
                    className="w-full pl-9 pr-4 py-2 rounded-xl bg-bg-tertiary border border-border-subtle text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 transition-colors"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectAll}
                  className="text-xs whitespace-nowrap"
                >
                  Select All
                </Button>
                {selectedChannelIds.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearAll}
                    className="text-xs text-danger hover:text-danger whitespace-nowrap"
                  >
                    Clear
                  </Button>
                )}
              </div>

              {/* Channel Stats */}
              <div className="flex items-center gap-4 px-1">
                <span className="text-xs text-text-muted">
                  {channels.length} channels available
                </span>
                {selectedChannelIds.length > 0 && (
                  <span className="text-xs text-success">
                    {selectedChannelIds.length} selected
                  </span>
                )}
                {searchQuery && (
                  <span className="text-xs text-accent">
                    {filteredChannels.length} matching
                  </span>
                )}
              </div>

              {/* Channel List */}
              <div className="max-h-72 overflow-y-auto space-y-2 pr-1 -mr-1">
                {filteredChannels.length === 0 ? (
                  <div className="p-6 text-center">
                    <Search className="w-8 h-8 mx-auto mb-2 text-text-muted opacity-50" />
                    <p className="text-sm text-text-muted">No channels found</p>
                  </div>
                ) : (
                  filteredChannels.map((channel, index) => {
                    const isSelected = selectedChannelIds.includes(channel.id);
                    return (
                      <motion.button
                        key={channel.id}
                        type="button"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.02 }}
                        onClick={() => handleToggleChannel(channel.id)}
                        className={cn(
                          "w-full p-3 rounded-xl text-left transition-all duration-150",
                          "flex items-center gap-3 group",
                          isSelected
                            ? "bg-accent/15 border border-accent/40"
                            : "bg-bg-tertiary/50 border border-transparent hover:bg-bg-tertiary hover:border-border-subtle"
                        )}
                      >
                        {/* Checkbox */}
                        <div
                          className={cn(
                            "w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0",
                            isSelected
                              ? "bg-accent border-accent"
                              : "border-border-default group-hover:border-accent/50"
                          )}
                        >
                          {isSelected && (
                            <Check className="w-3 h-3 text-bg-primary" />
                          )}
                        </div>

                        {/* Icon */}
                        <div
                          className={cn(
                            "w-9 h-9 rounded-lg flex items-center justify-center transition-colors flex-shrink-0",
                            channel.type === "channel"
                              ? isSelected
                                ? "bg-info/20 text-info"
                                : "bg-info/10 text-info/70 group-hover:text-info"
                              : isSelected
                                ? "bg-success/20 text-success"
                                : "bg-success/10 text-success/70 group-hover:text-success"
                          )}
                        >
                          {channel.type === "channel" ? (
                            <Radio className="w-4 h-4" />
                          ) : (
                            <Users className="w-4 h-4" />
                          )}
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <p
                            className={cn(
                              "text-sm font-medium truncate transition-colors",
                              isSelected ? "text-accent" : "text-text-primary"
                            )}
                          >
                            {channel.name}
                          </p>
                          <p className="text-xs text-text-muted truncate">
                            {channel.username
                              ? `@${channel.username}`
                              : channel.type === "channel"
                                ? "Private Channel"
                                : "Private Group"}
                          </p>
                        </div>

                        {/* Type Badge */}
                        <span
                          className={cn(
                            "text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full flex-shrink-0",
                            channel.type === "channel"
                              ? "bg-info/10 text-info"
                              : "bg-success/10 text-success"
                          )}
                        >
                          {channel.type}
                        </span>
                      </motion.button>
                    );
                  })
                )}
              </div>

              {/* Tip */}
              <div className="flex items-start gap-2 p-3 rounded-xl bg-accent/5 border border-accent/20">
                <Sparkles className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                <p className="text-xs text-text-muted">
                  <span className="text-accent font-medium">Tip:</span> Select
                  multiple channels to monitor. The bot will listen for signals
                  from all selected channels.
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-3 rounded-xl bg-danger/10 border border-danger/30 flex items-start gap-2"
        >
          <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
          <p className="text-xs text-danger">{error}</p>
        </motion.div>
      )}
    </div>
  );
}
