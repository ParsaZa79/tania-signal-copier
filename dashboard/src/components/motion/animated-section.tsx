import type { HTMLAttributes, ReactNode } from "react";

type AnimatedSectionProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  className?: string;
};

export function AnimatedSection({
  children,
  className,
  ...props
}: AnimatedSectionProps) {
  return (
    <div className={className} {...props}>
      {children}
    </div>
  );
}
