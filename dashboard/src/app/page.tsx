"use client";

import { ConnectedHome } from "@/components/dashboard/connected-home";
import { SetupHome } from "@/components/dashboard/setup-home";
import { useDashboard } from "@/components/layout/dashboard-layout";

export default function DashboardPage() {
  const { positions, account, accountPending, isConnected, reconnect, session, designPreview } =
    useDashboard();
  const needsSetup = !session.setupComplete || !session.activeAccountId;

  if (needsSetup) {
    return <SetupHome session={session} />;
  }

  return (
    <ConnectedHome
      account={account}
      accountPending={accountPending}
      accountId={session.activeAccountId}
      email={session.user.email}
      isConnected={isConnected}
      positions={positions}
      preview={designPreview}
      reconnect={reconnect}
    />
  );
}
