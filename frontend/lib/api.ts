const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

interface ProcessAnalyzeRequest {
  process_name: string;
  description: string;
  roi_input: {
    monthly_volume: number;
    minutes_per_transaction: number;
    employee_hourly_rate: number;
  };
  persist: boolean;
}

export interface ProcessAnalyzeResponse {
  analysis_id: string | null;
  status: string;
  analysis: {
    process_name: string;
    steps: Array<{
      name: string;
      description: string;
      is_manual: boolean;
    }>;
    approvals: string[];
    manual_tasks: string[];
  };
  bottlenecks: Array<{
    title: string;
    severity: "low" | "medium" | "high" | "critical";
    impact: string;
    recommendation: string;
  }>;
  opportunities: Array<{
    solution: string;
    technology: string;
    business_value: string;
    implementation_effort: "low" | "medium" | "high";
  }>;
  roi: {
    current_hours: number;
    estimated_hours_saved: number;
    monthly_savings: number;
    annual_savings: number;
    roi_score: number;
  };
  total_tokens: number;
  duration_ms: number;
}

interface ApiErrorResponse {
  error?: {
    message?: string;
  };
}

export async function analyzeProcess(
  payload: ProcessAnalyzeRequest,
): Promise<ProcessAnalyzeResponse> {
  const response = await fetch(`${API_URL}/api/v1/process/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorResponse | null;
    throw new Error(body?.error?.message ?? `Analysis failed (${response.status}).`);
  }

  return (await response.json()) as ProcessAnalyzeResponse;
}

export interface ReportGenerateResponse {
  analysis_id: string | null;
  report: string;
  total_tokens: number;
}

export async function generateExecutiveReport(
  analysisId: string,
): Promise<ReportGenerateResponse> {
  const response = await fetch(`${API_URL}/api/v1/report/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId }),
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorResponse | null;
    throw new Error(body?.error?.message ?? `Report generation failed (${response.status}).`);
  }

  return (await response.json()) as ReportGenerateResponse;
}