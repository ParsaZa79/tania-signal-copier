"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, MailPlus, Shield, Trash2, UserCheck } from "lucide-react";
import {
  deleteAccessMember,
  getAccessMembers,
  inviteAccessMember,
  updateAccessMember,
  type AccessMember,
} from "@/lib/api";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { useDashboard } from "@/components/layout/dashboard-layout";
import {
  PageHeader,
  PageLoading,
  PanelBody,
  PanelHeader,
  SectionPanel,
} from "@/components/layout";
import { AnimatedSection, PageContainer } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const ROLE_OPTIONS: AccessMember["role"][] = ["owner", "admin", "trader", "viewer"];

export default function AccessPage() {
  const { session } = useDashboard();
  const [members, setMembers] = useState<AccessMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<AccessMember["role"]>("trader");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isInviting, setIsInviting] = useState(false);
  const [workosInvitationsEnabled, setWorkosInvitationsEnabled] = useState(false);

  const canManage = session.user.role === "owner" || session.user.role === "admin";

  const loadMembers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getAccessMembers();
      setMembers(result.members);
      setWorkosInvitationsEnabled(result.workos.invitations_enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load access members");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  const activeCount = useMemo(
    () => members.filter((member) => member.status === "active").length,
    [members]
  );

  const handleInvite = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) return;

    setIsInviting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await inviteAccessMember(cleanEmail, role);
      setMembers(result.members);
      setEmail("");
      setRole("trader");
      setMessage(
        workosInvitationsEnabled
          ? `Invitation sent to ${cleanEmail}.`
          : `${cleanEmail} was added locally. WorkOS invitations need server credentials before email can be sent.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not invite member");
    } finally {
      setIsInviting(false);
    }
  };

  const handleUpdate = async (
    member: AccessMember,
    update: { role?: AccessMember["role"]; status?: AccessMember["status"] }
  ) => {
    setMessage(null);
    setError(null);
    try {
      const result = await updateAccessMember(member.id, update);
      setMembers(result.members);
      setMessage(`${member.email} updated.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update member");
    }
  };

  const handleDelete = async (member: AccessMember) => {
    setMessage(null);
    setError(null);
    try {
      const result = await deleteAccessMember(member.id);
      setMembers(result.members);
      setMessage(`${member.email} removed from dashboard access.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove member");
    }
  };

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="Security"
          title="Access"
          description="Manage who can sign in and which role they have in this dashboard"
          actions={
            <div className="flex items-center gap-2 rounded-xl border border-border-subtle bg-bg-tertiary/70 px-3 py-2">
              <Shield className="h-4 w-4 text-accent" />
              <span className="text-xs text-text-secondary">
                WorkOS AuthKit
              </span>
            </div>
          }
        />
      </AnimatedSection>

      {!workosInvitationsEnabled && (
        <AnimatedSection>
          <div className="rounded-xl border border-warning/30 bg-warning/10 p-4">
            <p className="text-sm font-medium text-warning">WorkOS invitations are not configured yet</p>
            <p className="mt-1 text-xs text-text-muted">
              Authentication code is ready, but the WorkOS server credentials are still required
              before invitation email delivery can be tested.
            </p>
          </div>
        </AnimatedSection>
      )}

      <AnimatedSection className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4">
        <SectionPanel>
          <PanelHeader
            eyebrow="Invite"
            title="Add email"
            description="Send a WorkOS invitation and grant app access"
          />
          <PanelBody>
            <form onSubmit={handleInvite} className="space-y-4">
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="person@example.com"
                disabled={!canManage || isInviting}
              />
              <Select
                label="Role"
                value={role}
                onValueChange={(nextRole) => setRole(nextRole as AccessMember["role"])}
                disabled={!canManage || isInviting}
                options={ROLE_OPTIONS.map((item) => ({ value: item, label: roleLabel(item) }))}
              />
              <Button type="submit" variant="accent" disabled={!canManage || isInviting || !email.trim()}>
                {isInviting ? <LoaderLabel label="Inviting" /> : <><MailPlus className="h-4 w-4" /> Invite</>}
              </Button>
            </form>
            {!canManage && (
              <p className="mt-4 text-xs text-text-muted">Only owners and admins can manage access.</p>
            )}
            {message && <p className="mt-4 text-xs text-success">{message}</p>}
            {error && <p className="mt-4 text-xs text-danger">{error}</p>}
          </PanelBody>
        </SectionPanel>

        <SectionPanel>
          <PanelHeader
            eyebrow="Members"
            title="Dashboard access"
            description={`${members.length} total · ${activeCount} active`}
            metric={{ label: "Active users", value: activeCount, tone: "accent" }}
          />
          <PanelBody flush>
            {isLoading ? (
              <PageLoading label="Loading access members…" className="min-h-[280px]" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="border-b border-border-subtle bg-bg-tertiary/40 text-left text-[10px] uppercase tracking-wider text-text-muted">
                    <tr>
                      <th className="px-5 py-3 font-medium">Email</th>
                      <th className="px-5 py-3 font-medium">Role</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium">WorkOS</th>
                      <th className="px-5 py-3 text-right font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {members.map((member) => (
                      <tr key={member.id} className="text-text-secondary">
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-subtle bg-bg-tertiary">
                              <UserCheck className="h-4 w-4 text-text-muted" />
                            </div>
                            <div>
                              <p className="font-medium text-text-primary">{member.email}</p>
                              <p className="text-[11px] text-text-muted">{member.id}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-4">
                          <Select
                            aria-label={`Role for ${member.email}`}
                            value={member.role}
                            disabled={!canManage}
                            onValueChange={(nextRole) =>
                              handleUpdate(member, { role: nextRole as AccessMember["role"] })
                            }
                            compact
                            containerClassName="w-36"
                            className="h-8 rounded-lg px-2 text-xs"
                            menuClassName="min-w-36"
                            options={ROLE_OPTIONS.map((item) => ({
                              value: item,
                              label: roleLabel(item),
                            }))}
                          />
                        </td>
                        <td className="px-5 py-4">
                          <StatusBadge status={member.status} />
                        </td>
                        <td className="px-5 py-4">
                          <span className="inline-flex items-center gap-1.5 text-xs text-text-muted">
                            <KeyRound className="h-3.5 w-3.5" />
                            {member.workos_user_id ? "Linked" : member.invitation_status || "Pending"}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={!canManage}
                              onClick={() =>
                                handleUpdate(member, {
                                  status: member.status === "active" ? "disabled" : "active",
                                })
                              }
                            >
                              {member.status === "active" ? "Disable" : "Enable"}
                            </Button>
                            <Button
                              size="icon"
                              variant="danger"
                              disabled={!canManage}
                              onClick={() => handleDelete(member)}
                              title="Remove access"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {members.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-5 py-12 text-center text-sm text-text-muted">
                          No access members yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>
    </PageContainer>
  );
}

function roleLabel(role: AccessMember["role"]) {
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function StatusBadge({ status }: { status: AccessMember["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2 py-1 text-[11px] font-medium capitalize",
        status === "active" && "border-success/30 bg-success/10 text-success",
        status === "pending" && "border-warning/30 bg-warning/10 text-warning",
        status === "disabled" && "border-danger/30 bg-danger/10 text-danger"
      )}
    >
      {status}
    </span>
  );
}

function LoaderLabel({ label }: { label: string }) {
  return (
    <>
      <IOSSpinner size={14} />
      {label}
    </>
  );
}
