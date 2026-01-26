"use client";

import { cn } from "@/lib/utils";
import { Wifi, WifiOff, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ConnectionStatusProps {
  isConnected: boolean;
  error: string | null;
  onReconnect: () => void;
}

export function ConnectionStatus({
  isConnected,
  error,
  onReconnect,
}: ConnectionStatusProps) {
  if (isConnected && !error) return null;

  return (
    <div
      className={cn(
        "flex items-center justify-between p-4 rounded-lg mb-6",
        isConnected ? "bg-yellow-50 border border-yellow-200" : "bg-red-50 border border-red-200"
      )}
    >
      <div className="flex items-center gap-3">
        {isConnected ? (
          <Wifi className="w-5 h-5 text-yellow-600" />
        ) : (
          <WifiOff className="w-5 h-5 text-red-600" />
        )}
        <div>
          <p
            className={cn(
              "font-medium",
              isConnected ? "text-yellow-800" : "text-red-800"
            )}
          >
            {isConnected ? "Connection Issue" : "Disconnected"}
          </p>
          <p
            className={cn(
              "text-sm",
              isConnected ? "text-yellow-600" : "text-red-600"
            )}
          >
            {error || "Unable to connect to trading server"}
          </p>
        </div>
      </div>
      <Button size="sm" variant="outline" onClick={onReconnect}>
        <RefreshCw className="w-4 h-4 mr-2" />
        Reconnect
      </Button>
    </div>
  );
}
