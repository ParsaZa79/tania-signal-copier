"use client";

import { useState } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { LockKeyhole } from "lucide-react";
import { resetPassword } from "@/app/auth/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthShell } from "./auth-shell";

interface WorkOSResetPasswordFormProps {
  token: string;
}

export function WorkOSResetPasswordForm({ token }: WorkOSResetPasswordFormProps) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await resetPassword(token, password);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      window.location.assign(result.redirectTo);
    } catch {
      setError("Unable to update your password. Request a new reset link.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <header>
        <h1 id="reset-title" className="text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          Choose a new password
        </h1>
        <p className="mt-2 text-lg text-[#85858d]">Use at least 10 characters.</p>
      </header>
      <form className="mt-10 space-y-6" onSubmit={submit} aria-labelledby="reset-title">
        <Input
          label="New password"
          labelClassName="mb-2.5 text-sm normal-case tracking-normal text-[#c7c7cc]"
          className="h-14 border-white/[0.11] bg-[#09090b]/80 text-[15px] placeholder:text-[#5f5f67]"
          leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="Enter a new password"
          type="password"
          autoComplete="new-password"
          minLength={10}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Input
          label="Confirm password"
          labelClassName="mb-2.5 text-sm normal-case tracking-normal text-[#c7c7cc]"
          className="h-14 border-white/[0.11] bg-[#09090b]/80 text-[15px] placeholder:text-[#5f5f67]"
          leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="Enter it once more"
          type="password"
          autoComplete="new-password"
          minLength={10}
          required
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        {error ? (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </p>
        ) : null}
        <Button
          className="h-14 w-full bg-[#829cff] text-[15px] text-[#08090d] hover:bg-[#9aafff]"
          variant="accent"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? <IOSSpinner size={16} /> : null}
          {isSubmitting ? "Updating…" : "Update password"}
        </Button>
      </form>
    </AuthShell>
  );
}
