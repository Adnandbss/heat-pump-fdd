type Props = {
  className?: string;
};

export function Skeleton({ className = "" }: Props) {
  return <div className={`bg-white/5 animate-pulse rounded-[1.5rem] ${className}`} aria-hidden />;
}
