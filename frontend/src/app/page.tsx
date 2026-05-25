import {
  TrendingUp,
  FileText,
  Target,
  AlertTriangle,
  CheckCircle,
  Info,
} from "lucide-react";
import { api } from "@/lib/api-client";
import type { DashboardStats } from "@/types";
import { formatPercent, formatDate } from "@/lib/utils";
import DashboardWinRate from "./dashboard-win-rate";
import ActiveDebateCard from "./active-debate-card";

async function getDashboardStats(): Promise<DashboardStats | null> {
  try {
    return await api.get<DashboardStats>("/api/dashboard");
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const stats = await getDashboardStats();

  // Fallback data when API is unavailable
  const data: DashboardStats = stats ?? {
    latest_report: null,
    open_recommendations: 0,
    weekly_win_rate: 0,
    weekly_closed: 0,
    alerts: [],
  };

  const statCards = [
    {
      label: "Open Recs",
      value: data.open_recommendations.toString(),
      icon: <FileText size={20} className="text-blue-400" />,
      color: "text-blue-400",
    },
    {
      label: "Weekly Closed",
      value: data.weekly_closed.toString(),
      icon: <CheckCircle size={20} className="text-emerald-400" />,
      color: "text-emerald-400",
    },
    {
      label: "Win Rate (7d)",
      value: formatPercent(data.weekly_win_rate),
      icon: <Target size={20} className="text-yellow-400" />,
      color: "text-yellow-400",
    },
    {
      label: "Latest Report",
      value: data.latest_report
        ? formatDate(data.latest_report.date)
        : "None",
      icon: <TrendingUp size={20} className="text-purple-400" />,
      color: "text-purple-400",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Overview of your daily report pipeline
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <div key={card.label} className="card">
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--text-secondary)]">
                {card.label}
              </p>
              {card.icon}
            </div>
            <p className={`mt-2 text-2xl font-bold ${card.color}`}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Active debate widget */}
      <ActiveDebateCard />

      {/* Win rate gauge & alerts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Win rate */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
            Win Rate
          </h2>
          <div className="flex items-center justify-center">
            <DashboardWinRate value={data.weekly_win_rate} />
          </div>
        </div>

        {/* Alerts */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
            Alerts
          </h2>
          {data.alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-[var(--text-secondary)]">
              <CheckCircle size={32} className="mb-2 text-emerald-400" />
              <p className="text-sm">No alerts at this time</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.alerts.map((alert) => {
                const isPositive =
                  alert.pnl_percent !== null && alert.pnl_percent > 0;
                return (
                  <div
                    key={`${alert.ticker}-${alert.status}`}
                    className="flex items-start gap-3 rounded-lg bg-[var(--bg-hover)] p-3"
                  >
                    {alert.status === "STOP_HIT" ? (
                      <AlertTriangle size={16} className="text-red-400" />
                    ) : (
                      <Info
                        size={16}
                        className={
                          isPositive ? "text-emerald-400" : "text-yellow-400"
                        }
                      />
                    )}
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {alert.ticker} — {alert.name} ({alert.status})
                      </p>
                      {alert.pnl_percent !== null && (
                        <p
                          className={`text-xs ${isPositive ? "text-emerald-400" : "text-red-400"}`}
                        >
                          {isPositive ? "+" : ""}
                          {alert.pnl_percent.toFixed(2)}%
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
