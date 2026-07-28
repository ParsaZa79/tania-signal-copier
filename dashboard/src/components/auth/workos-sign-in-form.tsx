"use client";

import Link from "next/link";
import { useState } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { ArrowLeft, LockKeyhole, Mail } from "lucide-react";
import { requestPasswordReset, signInWithPassword } from "@/app/auth/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthShell } from "./auth-shell";
import { GoogleSignInButton } from "./google-sign-in-button";

const fieldClass =
  "h-14 border-white/[0.11] bg-[#09090b]/80 text-[15px] placeholder:text-[#5f5f67] hover:border-white/[0.16] focus:border-[#829cff]/70 focus:ring-[#829cff]/15";
const labelClass = "mb-2.5 text-sm normal-case tracking-normal text-[#c7c7cc]";
const primaryClass =
  "h-14 w-full bg-[#829cff] text-[15px] text-[#08090d] shadow-[0_10px_35px_rgba(92,120,255,0.18)] hover:bg-[#9aafff]";

interface WorkOSSignInFormProps {
  returnTo?: string;
  invitationToken?: string;
  initialError?: string | null;
  resetComplete?: boolean;
}

function signUpHref(returnTo?: string, invitationToken?: string) {
  const search = new URLSearchParams();
  if (returnTo) search.set("returnTo", returnTo);
  if (invitationToken) search.set("invitation_token", invitationToken);
  const query = search.toString();
  return query ? `/sign-up?${query}` : "/sign-up";
}

export function WorkOSSignInForm({
  returnTo,
  invitationToken,
  initialError,
  resetComplete = false,
}: WorkOSSignInFormProps) {
  const [forgot, setForgot] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(
    resetComplete ? "Password updated. You can now sign in." : null,
  );
  const [error, setError] = useState<string | null>(initialError ?? null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    setMessage(null);

    try {
      if (forgot) {
        const result = await requestPasswordReset(email);
        if (result.ok) setMessage(result.message);
        else setError(result.error);
        return;
      }

      const result = await signInWithPassword({
        email,
        password,
        returnTo,
        invitationToken,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      window.location.assign(result.redirectTo);
    } catch {
      setError(forgot ? "Unable to request a password reset." : "Unable to sign in.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <header>
        {forgot ? (
          <button
            type="button"
            onClick={() => {
              setForgot(false);
              setError(null);
              setMessage(null);
            }}
            className="mb-7 inline-flex items-center gap-2 rounded-md text-sm text-[#9d9da5] hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </button>
        ) : null}
        <h1 id="auth-title" className="text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          {forgot ? "Reset your password" : "Welcome back"}
        </h1>
        <p className="mt-2 text-lg text-[#85858d]">
          {forgot ? "We’ll send a reset link if the account exists." : "Sign in to continue"}
        </p>
      </header>

      <form className="mt-10 space-y-6" onSubmit={submit} aria-labelledby="auth-title">
        <Input
          label="Email address"
          labelClassName={labelClass}
          className={fieldClass}
          leadingIcon={<Mail className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="you@example.com"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />

        {!forgot ? (
          <div>
            <Input
              label="Password"
              labelClassName={labelClass}
              className={fieldClass}
              leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
              placeholder="Enter your password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                className="rounded-md text-sm font-medium text-[#829cff] hover:text-[#aab9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                onClick={() => {
                  setForgot(true);
                  setError(null);
                  setMessage(null);
                }}
              >
                Forgot password?
              </button>
            </div>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm leading-relaxed text-danger">
            {error}
          </p>
        ) : null}
        {message ? (
          <p role="status" className="rounded-xl border border-success/25 bg-success/10 px-4 py-3 text-sm leading-relaxed text-success">
            {message}
          </p>
        ) : null}

        <Button className={primaryClass} variant="accent" type="submit" disabled={isSubmitting}>
          {isSubmitting ? <IOSSpinner size={16} /> : null}
          {isSubmitting ? "Please wait…" : forgot ? "Send reset link" : "Sign in"}
        </Button>
      </form>

      {!forgot ? (
        <>
          <div className="my-7 flex items-center gap-3">
            <div className="h-px flex-1 bg-white/[0.08]" />
            <span className="text-xs uppercase tracking-[0.18em] text-[#686870]">or</span>
            <div className="h-px flex-1 bg-white/[0.08]" />
          </div>
          <GoogleSignInButton
            mode="sign-in"
            returnTo={returnTo}
            invitationToken={invitationToken}
            loginHint={email}
          />
          <p className="mt-6 text-center text-sm text-[#92929a]">
            New here?{" "}
            <Link
              className="rounded-md font-medium text-[#829cff] hover:text-[#aab9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
              href={signUpHref(returnTo, invitationToken)}
            >
              Create account
            </Link>
          </p>
        </>
      ) : null}
    </AuthShell>
  );
}
