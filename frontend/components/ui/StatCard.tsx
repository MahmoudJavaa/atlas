import { clsx } from "clsx";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function StatCard({ label, value, sub, trend, className }: StatCardProps) {
  return (
    <div className={clsx("card", className)}>
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && (
        <p
          className={clsx(
            "text-xs mt-1",
            trend === "up" && "text-green-400",
            trend === "down" && "text-red-400",
            trend === "neutral" && "text-gray-500",
            !trend && "text-gray-500"
          )}
        >
          {sub}
        </p>
      )}
    </div>
  );
}
