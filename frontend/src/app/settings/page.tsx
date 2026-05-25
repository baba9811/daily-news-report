import { Settings as SettingsIcon } from "lucide-react";
import { api } from "@/lib/api-client";
import type { SettingsData, SystemStatus } from "@/types";
import SettingsForm from "./settings-form";
import SystemStatusPanel from "./system-status";
import MultiAgentStatus from "./multi-agent-status";
import MulticaStatusPanel from "./multica-status";

async function getSettings(): Promise<SettingsData | null> {
  try {
    return await api.get<SettingsData>("/api/settings");
  } catch {
    return null;
  }
}

async function getSystemStatus(): Promise<SystemStatus | null> {
  try {
    return await api.get<SystemStatus>("/api/settings/status");
  } catch {
    return null;
  }
}

export default async function SettingsPage() {
  const [settings, status] = await Promise.all([
    getSettings(),
    getSystemStatus(),
  ]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          Settings
        </h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Configure email, AI model, and system settings
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Settings form */}
        <div className="lg:col-span-2">
          {settings ? (
            <SettingsForm initialSettings={settings} />
          ) : (
            <div className="card flex flex-col items-center justify-center py-16">
              <SettingsIcon
                size={48}
                className="mb-4 text-[var(--text-secondary)]"
              />
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                Unable to load settings
              </h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Make sure the backend server is running.
              </p>
            </div>
          )}
        </div>

        {/* System status + multi-agent + Multica */}
        <div className="space-y-6">
          <SystemStatusPanel status={status} />
          <MultiAgentStatus />
          <MulticaStatusPanel />
        </div>
      </div>
    </div>
  );
}
