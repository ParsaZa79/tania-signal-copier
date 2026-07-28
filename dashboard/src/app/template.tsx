export default function Template({ children }: { children: React.ReactNode }) {
  // Keep the route boundary paint-stable. Fading this full-size wrapper forces
  // Safari and Firefox to repeatedly re-composite the entire scrollable page
  // while initial account data and skeletons are settling.
  return <>{children}</>;
}
