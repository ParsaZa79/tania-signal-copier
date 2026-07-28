"use client";

import Link from "next/link";
import { useState } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { LockKeyhole, Mail, UserRound } from "lucide-react";
import { signUpWithPassword } from "@/app/auth/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthShell } from "./auth-shell";
import { GoogleSignInButton } from "./google-sign-in-button";

const fieldClass =
  "h-14 border-white/[0.11] bg-[#09090b]/80 text-[15px] placeholder:text-[#5f5f67] hover:border-white/[0.16] focus:border-[#829cff]/70 focus:ring-[#829cff]/15";
const labelClass = "mb-2.5 text-sm normal-case tracking-normal text-[#c7c7cc]";
const primaryClass =
  "h-14 w-full bg-[#829cff] text-[15px] text-[#08090d] shadow-[0_10px_35px_rgba(92,120,255,0.18)] hover:bg-[#9aafff]";

interface WorkOSSignUpFormProps {
  returnTo?: string;
  invitationToken?: string;
}

function signInHref(returnTo?: string, invitationToken?: string) {
  const search = new URLSearchParams();
  if (returnTo) search.set("returnTo", returnTo);
  if (invitationToken) search.set("invitation_token", invitationToken);
  const query = search.toString();
  return query ? `/sign-in?${query}` : "/sign-in";
}

export function WorkOSSignUpForm({ returnTo, invitationToken }: WorkOSSignUpFormProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await signUpWithPassword({
        name,
        email,
        password,
        confirmPassword,
        returnTo,
        invitationToken,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      window.location.assign(result.redirectTo);
    } catch {
      setError("Unable to create your account. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <header>
        <h1 id="signup-title" className="text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          Create your account
        </h1>
        <p className="mt-2 text-lg text-[#85858d]">Start with a few simple details</p>
      </header>

      <form className="mt-9 space-y-5" onSubmit={submit} aria-labelledby="signup-title">
        <Input
          label="Your name"
          labelClassName={labelClass}
          className={fieldClass}
          leadingIcon={<UserRound className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="How should we address you?"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
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
        <Input
          label="Password"
          labelClassName={labelClass}
          className={fieldClass}
          leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="Create a secure password"
          type="password"
          autoComplete="new-password"
          minLength={10}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Input
          label="Confirm password"
          labelClassName={labelClass}
          className={fieldClass}
          leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="Enter it once more"
          type="password"
          autoComplete="new-password"
          minLength={10}
          required
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        <p className="text-xs text-[#73737b]">
          Use at least 10 characters. WorkOS also blocks weak and breached passwords.
        </p>

        {error ? (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm leading-relaxed text-danger">
            {error}
          </p>
        ) : null}

        <Button className={primaryClass} variant="accent" type="submit" disabled={isSubmitting}>
          {isSubmitting ? <IOSSpinner size={16} /> : null}
          {isSubmitting ? "Creating…" : "Create account"}
        </Button>
      </form>

      <div className="my-7 flex items-center gap-3">
        <div className="h-px flex-1 bg-white/[0.08]" />
        <span className="text-xs uppercase tracking-[0.18em] text-[#686870]">or</span>
        <div className="h-px flex-1 bg-white/[0.08]" />
      </div>
      <GoogleSignInButton
        mode="sign-up"
        returnTo={returnTo}
        invitationToken={invitationToken}
        loginHint={email}
      />

      <p className="mt-6 text-center text-sm text-[#92929a]">
        Already have an account?{" "}
        <Link
          className="rounded-md font-medium text-[#829cff] hover:text-[#aab9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          href={signInHref(returnTo, invitationToken)}
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
