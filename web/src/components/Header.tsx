import { PAGE_COPY } from "../lib";

type Props = {
  page: string;
};

export function Header({ page }: Props) {
  const copy = PAGE_COPY[page] ?? PAGE_COPY.fleet;
  return (
    <header className="mb-7">
      <h1 className="text-[2rem] font-semibold tracking-tight leading-none">{copy.title}</h1>
      <p className="text-sm text-white/55 mt-2">{copy.subtitle}</p>
    </header>
  );
}
