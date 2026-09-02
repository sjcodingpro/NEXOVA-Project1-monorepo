const COMPANY_SNAPSHOT = [
  { label: "Founded", value: "2011" },
  { label: "Employees", value: "~120" },
  { label: "Annual revenue", value: "$8M" },
  { label: "Headquarters", value: "Valencia, Spain" },
  { label: "Expansion office", value: "Miami, Florida" },
];

const BUSINESS_LINES = [
  "Executive and mid-management headhunting",
  "Customer support team outsourcing for technology companies",
  "Corporate training in soft skills and leadership",
];

export default function BackofficePage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold">Welcome to the Nexova Backoffice</h1>
      <p className="text-slate-400 text-sm mt-2 max-w-xl">
        Internal operations hub for Nexova. This is the starting shell —
        people management, recruiting operations, and other internal
        tooling will live here as the platform grows.
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
          Company snapshot
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {COMPANY_SNAPSHOT.map((item) => (
            <div
              key={item.label}
              className="border border-slate-800 rounded-lg px-4 py-3 bg-slate-900/50"
            >
              <p className="text-xs text-slate-500">{item.label}</p>
              <p className="text-lg font-semibold mt-1">{item.value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
          Business lines
        </h2>
        <ul className="space-y-2">
          {BUSINESS_LINES.map((line) => (
            <li
              key={line}
              className="border border-slate-800 rounded-lg px-4 py-3 bg-slate-900/50 text-sm"
            >
              {line}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
