import Link from "next/link";
import { ArrowLeft, ExternalLink, MessageSquare } from "lucide-react";
import { api } from "@/lib/api-client";
import type { ReportDetail } from "@/types";
import { formatDate } from "@/lib/utils";
import ReportHtmlViewer from "./report-html-viewer";

interface ReportDetailPageProps {
  params: Promise<{ id: string }>;
}

async function getReport(id: string): Promise<ReportDetail | null> {
  try {
    return await api.get<ReportDetail>(`/api/reports/${id}`);
  } catch {
    return null;
  }
}

export default async function ReportDetailPage({
  params,
}: ReportDetailPageProps) {
  const { id } = await params;
  const report = await getReport(id);

  if (!report) {
    return (
      <div className="space-y-6">
        <Link
          href="/reports"
          className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft size={16} />
          Back to Reports
        </Link>
        <div className="card flex flex-col items-center justify-center py-16">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Report not found
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            This report may have been removed or does not exist.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/reports"
        className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <ArrowLeft size={16} />
        Back to Reports
      </Link>

      {/* Report header */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {report.report_type === "daily" ? "Daily Report" : "Weekly Report"}
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {formatDate(report.report_date)}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {report.generation_time_s !== null && (
              <span className="text-sm text-[var(--text-secondary)]">
                Generated in {report.generation_time_s.toFixed(1)}s
              </span>
            )}
            <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-medium text-emerald-400">
              {report.report_type}
            </span>
          </div>
        </div>
        {report.summary && (
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            {report.summary}
          </p>
        )}
        {(() => {
          const debateId = (report as ReportDetail & { debate_id?: string | null })
            .debate_id;
          if (!debateId) return null;
          return (
            <Link
              href={`/debate/${debateId}`}
              className="mt-3 inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
            >
              <MessageSquare size={14} />
              View debate
            </Link>
          );
        })()}
      </div>

      {/* HTML report viewer */}
      {report.html_content && (
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              Full Report
            </h2>
            <a
              href={`/api/reports/${report.id}/html`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
            >
              Open in new tab
              <ExternalLink size={14} />
            </a>
          </div>
          <ReportHtmlViewer
            reportId={report.id}
            languages={[
              report.language ?? "ko",
              ...(report.translations ?? []).map((t) => t.language),
            ]}
          />
        </div>
      )}
    </div>
  );
}
