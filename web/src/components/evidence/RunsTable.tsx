import { useMemo, useState } from "react";
import type { EvidenceRuns, RunRow } from "../../api";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";
import { SelectField } from "../Fields";

type SortKey = keyof RunRow;
type Props = {
  data?: EvidenceRuns;
  experiment: string;
  protocol: string;
  model: string;
  label: string;
  onFilter: (next: { experiment: string; protocol: string; model: string; label: string }) => void;
  onMore: () => void;
};

const COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: "experiment", label: "Exp" },
  { key: "protocol", label: "Protocol" },
  { key: "reference", label: "Reference" },
  { key: "features", label: "Features" },
  { key: "model", label: "Model" },
  { key: "label", label: "Class" },
  { key: "metric", label: "Metric" },
  { key: "value", label: "Value" },
  { key: "n", label: "n" },
];

export function RunsTable({ data, experiment, protocol, model, label, onFilter, onMore }: Props) {
  const [sort, setSort] = useState<{ key: SortKey; dir: number }>({ key: "experiment", dir: 1 });
  const rows = useMemo(() => {
    const copy = [...(data?.rows ?? [])];
    copy.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sort.dir;
      return String(av).localeCompare(String(bv)) * sort.dir;
    });
    return copy;
  }, [data, sort]);

  const options = (values: string[] | undefined, allLabel: string) => [
    { value: "", label: allLabel },
    ...(values ?? []).map((value) => ({ value, label: value })),
  ];

  return (
    <GlassCard className="p-6" data-testid="runs-table">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Logged measurements</h2>
          <p className="text-xs text-white/45 mt-1">
            {data ? `${data.total} rows in ` : ""}
            <a className="underline decoration-white/20 hover:decoration-white/60" href="/api/evidence/runs?limit=50">
              {data?.csv_path ?? "outputs/results.csv"}
            </a>
          </p>
        </div>
        {rows[0] ? (
          <ProtocolBadge
            protocol={{
              experiment: rows[0].experiment,
              protocol: rows[0].protocol,
              reference: rows[0].reference,
              features: rows[0].features,
              model: rows[0].model,
            }}
          />
        ) : null}
      </div>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <SelectField
          label="Experiment"
          value={experiment}
          options={options(data?.experiments, "All experiments")}
          onChange={(value) => onFilter({ experiment: value, protocol, model, label })}
        />
        <SelectField
          label="Protocol"
          value={protocol}
          options={options(data?.protocols, "All protocols")}
          onChange={(value) => onFilter({ experiment, protocol: value, model, label })}
        />
        <SelectField
          label="Model"
          value={model}
          options={options(data?.models, "All models")}
          onChange={(value) => onFilter({ experiment, protocol, model: value, label })}
        />
        <SelectField
          label="Class"
          value={label}
          options={options(data?.labels, "All classes")}
          onChange={(value) => onFilter({ experiment, protocol, model, label: value })}
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-white/40">
            <tr>
              {COLUMNS.map((col) => (
                <th key={col.key} className="text-left font-medium pb-2 pr-3">
                  <button
                    type="button"
                    className="hover:text-white/80"
                    onClick={() =>
                      setSort((prev) => ({
                        key: col.key,
                        dir: prev.key === col.key ? -prev.dir : 1,
                      }))
                    }
                  >
                    {col.label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.experiment}-${row.protocol}-${row.reference}-${row.features}-${row.model}-${row.label}-${row.metric}-${index}`} className="border-t border-white/8">
                <td className="py-1.5 pr-3">{row.experiment}</td>
                <td className="py-1.5 pr-3">{row.protocol}</td>
                <td className="py-1.5 pr-3 max-w-[9rem] truncate">{row.reference}</td>
                <td className="py-1.5 pr-3">{row.features}</td>
                <td className="py-1.5 pr-3">{row.model}</td>
                <td className="py-1.5 pr-3">{row.label}</td>
                <td className="py-1.5 pr-3">{row.metric}</td>
                <td className="py-1.5 pr-3 tabular-nums">{row.value.toFixed(3)}</td>
                <td className="py-1.5 pr-3 tabular-nums">{row.n ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && data.offset + data.rows.length < data.total ? (
        <button
          type="button"
          onClick={onMore}
          className="mt-4 rounded-full border border-white/18 bg-white/10 px-4 py-2 text-xs text-white/80 hover:bg-white/16"
        >
          Load 50 more
        </button>
      ) : null}
    </GlassCard>
  );
}
