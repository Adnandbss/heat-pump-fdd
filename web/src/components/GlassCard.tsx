import type { HTMLAttributes, ReactNode } from "react";

type Props = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  className?: string;
};

export function GlassCard({ children, className = "", ...rest }: Props) {
  return (
    <div className={`glass transition-opacity duration-200 ${className}`} {...rest}>
      {children}
    </div>
  );
}
