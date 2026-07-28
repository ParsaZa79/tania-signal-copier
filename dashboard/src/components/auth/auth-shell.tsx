import Link from "next/link";
import type { ReactNode } from "react";
import { Link2, ShieldCheck, TrendingUp, UserRoundSearch } from "lucide-react";

const journey = [
  { title: "Connect account", description: "Link your MT5 account in minutes.", icon: Link2 },
  { title: "Choose a trader", description: "Browse verified trading histories.", icon: UserRoundSearch },
  { title: "Set your limits", description: "Control risk with clear safeguards.", icon: ShieldCheck },
] as const;

interface AuthShellProps {
  children: ReactNode;
}

export function AuthShell({ children }: AuthShellProps) {
  return (
    <main className="min-h-dvh overflow-hidden bg-[#050506] text-text-primary">
      <div className="grid min-h-dvh w-full lg:grid-cols-2">
        <section className="relative hidden min-h-dvh overflow-hidden border-r border-white/[0.09] lg:flex lg:flex-col lg:px-[clamp(3.5rem,6vw,6.75rem)] lg:py-[clamp(3.5rem,6vh,5.5rem)] [@media(max-height:800px)]:py-8">
          <div
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_70%_at_5%_38%,rgba(50,97,220,0.42),transparent_62%),radial-gradient(ellipse_55%_48%_at_42%_72%,rgba(38,86,201,0.16),transparent_68%),linear-gradient(135deg,#050506_0%,#071020_48%,#050506_100%)]"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute inset-0 opacity-25 [background-image:linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] [background-size:48px_48px]"
            aria-hidden="true"
          />

          <Link
            href="/"
            aria-label="Signal Copier home"
            className="relative z-10 flex w-fit items-center gap-3 rounded-lg text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <TrendingUp className="h-10 w-10 text-[#829cff]" strokeWidth={2.35} />
            <span className="text-[clamp(1.5rem,2vw,2rem)] font-semibold tracking-[-0.035em]">
              Signal Copier
            </span>
          </Link>

          <div className="relative z-10 mt-[clamp(5.5rem,12vh,9.5rem)] max-w-[670px] [@media(max-height:800px)]:mt-12">
            <h2 className="max-w-[650px] text-[clamp(3.1rem,4.45vw,4.65rem)] font-semibold leading-[0.99] tracking-[-0.055em] text-[#f7f7f9]">
              <span className="block">Copy trades with</span>
              <span className="block">limits you understand.</span>
            </h2>
            <p className="mt-8 max-w-[540px] text-[clamp(1.05rem,1.55vw,1.35rem)] leading-relaxed text-[#a6a6ad] [@media(max-height:800px)]:mt-5">
              Connect your MT5 account, choose who to copy, and stay in control.
            </p>
          </div>

          <ol className="relative z-10 mt-[clamp(8rem,20vh,13rem)] grid max-w-[760px] grid-cols-3 gap-6 [@media(max-height:800px)]:mt-auto [@media(max-height:800px)]:pt-6">
            {journey.map(({ title, description, icon: Icon }, index) => (
              <li key={title} className="relative min-w-0 text-center">
                {index < journey.length - 1 ? (
                  <span
                    aria-hidden="true"
                    className="absolute left-[calc(50%+2.75rem)] top-9 w-[calc(100%-3.5rem)] border-t border-dashed border-white/20"
                  />
                ) : null}
                <span className="mx-auto flex h-[74px] w-[74px] items-center justify-center rounded-full border border-white/25 bg-black/20 text-[#829cff] backdrop-blur-sm">
                  <Icon className="h-7 w-7" strokeWidth={1.7} />
                </span>
                <span className="mt-5 block text-sm font-semibold text-[#8da5ff]">{index + 1}</span>
                <span className="mt-2 block text-base font-medium text-text-primary">{title}</span>
                <span className="mx-auto mt-1 block max-w-[180px] text-sm leading-snug text-[#8a8a92]">
                  {description}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section className="relative flex min-h-dvh items-center px-6 py-12 sm:px-10 lg:px-[clamp(3.5rem,5vw,5.5rem)] [@media(max-height:800px)]:py-8">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-[radial-gradient(ellipse_80%_100%_at_20%_0%,rgba(67,111,225,0.3),transparent_70%)] lg:hidden"
            aria-hidden="true"
          />
          <div className="relative z-10 mx-auto w-full max-w-[520px]">
            <Link
              href="/"
              aria-label="Signal Copier home"
              className="mb-14 flex w-fit items-center gap-2.5 rounded-lg text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 lg:hidden"
            >
              <TrendingUp className="h-8 w-8 text-[#829cff]" strokeWidth={2.35} />
              <span className="text-xl font-semibold tracking-[-0.035em]">Signal Copier</span>
            </Link>

            {children}
          </div>
        </section>
      </div>
    </main>
  );
}
