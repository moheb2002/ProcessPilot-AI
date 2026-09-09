"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Coins,
  Download,
  FileText,
  Gauge,
  Lightbulb,
  Loader2,
  Play,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  TriangleAlert,
  Users,
  WandSparkles,
  Workflow,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { analyzeProcess, generateExecutiveReport } from "@/lib/api";

const exampleProcess = `Customer support escalation process:
1. A support engineer receives a high-priority customer case by email.
2. The engineer manually copies case details into a tracking sheet.
3. A team lead reviews the case and requests missing information through Teams.
4. The engineer prepares a summary and emails it to the incident manager.
5. The incident manager assigns the case to a specialist.
6. Status updates are manually collected and sent to stakeholders every two hours.
7. After resolution, the engineer writes a closure summary and updates three systems.`;

const navItems = ["Analyze", "Insights", "Roadmap"];

type Tab = (typeof navItems)[number];
type Tone = "blue" | "violet" | "emerald" | "amber";
type AnalysisStatus = "idle" | "loading" | "done";
type ReportStatus = "idle" | "loading" | "done";

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  detail: string;
  tone?: Tone;
}

interface StepProps {
  number: string;
  title: string;
  subtitle: string;
  active: boolean;
  complete: boolean;
}

interface AnalysisResult {
  analysisId: string;
  score: number;
  steps: number;
  manualTasks: number;
  approvals: number;
  currentHours: number;
  hoursSaved: number;
  monthlyValue: number;
  annualValue: number;
  bottlenecks: Array<{
    title: string;
    severity: string;
    detail: string;
  }>;
  recommendations: Array<{
    name: string;
    technology: string;
    impact: string;
    effort: string;
    icon: LucideIcon;
  }>;
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = "blue",
}: MetricCardProps) {
  const tones = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    violet: "bg-violet-50 text-violet-700 border-violet-100",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
  };
  return (
    <Card className="rounded-2xl border-slate-200 shadow-sm">
      <CardContent className="p-5">
        <div
          className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl border ${tones[tone]}`}
        >
          <Icon className="h-5 w-5" />
        </div>
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <p className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
          {value}
        </p>
        <p className="mt-1 text-xs text-slate-500">{detail}</p>
      </CardContent>
    </Card>
  );
}

function Step({ number, title, subtitle, active, complete }: StepProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${complete ? "bg-emerald-500 text-white" : active ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"}`}
      >
        {complete ? <CheckCircle2 className="h-5 w-5" /> : number}
      </div>
      <div>
        <p
          className={`text-sm font-semibold ${active || complete ? "text-slate-900" : "text-slate-500"}`}
        >
          {title}
        </p>
        <p className="text-xs text-slate-400">{subtitle}</p>
      </div>
    </div>
  );
}

export default function ProcessPilotMVP() {
  const [description, setDescription] = useState("");
  const [processName, setProcessName] = useState("Support Escalation");
  const [volume, setVolume] = useState(500);
  const [minutes, setMinutes] = useState(35);
  const [hourlyCost, setHourlyCost] = useState(20);
  const [activeTab, setActiveTab] = useState<Tab>("Analyze");
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reportStatus, setReportStatus] = useState<ReportStatus>("idle");
  const [report, setReport] = useState("");
  const [reportError, setReportError] = useState<string | null>(null);

  const analyze = async () => {
    if (description.trim().length < 20 || processName.trim().length < 2) return;
    setStatus("loading");
    setResult(null);
    setError(null);

    try {
      const response = await analyzeProcess({
        process_name: processName.trim(),
        description: description.trim(),
        roi_input: {
          monthly_volume: Math.max(0, Math.round(volume)),
          minutes_per_transaction: Math.max(0, minutes),
          employee_hourly_rate: Math.max(0, hourlyCost),
        },
        persist: true,
      });
      const automationRate = response.roi.current_hours
        ? response.roi.estimated_hours_saved / response.roi.current_hours
        : 0;

      if (!response.analysis_id) {
        throw new Error(
          "The analysis was not saved, so a report cannot be generated.",
        );
      }

      setResult({
        analysisId: response.analysis_id,
        score: Math.round(automationRate * 100),
        steps: response.analysis.steps.length,
        manualTasks: response.analysis.manual_tasks.length,
        approvals: response.analysis.approvals.length,
        currentHours: response.roi.current_hours,
        hoursSaved: response.roi.estimated_hours_saved,
        monthlyValue: response.roi.monthly_savings,
        annualValue: response.roi.annual_savings,
        bottlenecks: response.bottlenecks.map(item => ({
          title: item.title,
          severity: `${item.severity[0].toUpperCase()}${item.severity.slice(1)} impact`,
          detail: item.impact || item.recommendation,
        })),
        recommendations: response.opportunities.map(item => ({
          name: item.solution,
          technology: item.technology,
          impact: item.business_value,
          effort: `${item.implementation_effort[0].toUpperCase()}${item.implementation_effort.slice(1)}`,
          icon: item.technology.toLowerCase().includes("power automate")
            ? Workflow
            : item.technology.toLowerCase().includes("openai")
              ? BrainCircuit
              : WandSparkles,
        })),
      });
      setStatus("done");
      setActiveTab("Insights");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to connect to the analysis service.",
      );
      setStatus("idle");
    }
  };

  const generateReport = async () => {
    if (!result) return;
    setReportStatus("loading");
    setReportError(null);

    try {
      const response = await generateExecutiveReport(result.analysisId);
      setReport(response.report);
      setReportStatus("done");
    } catch (caughtError) {
      setReportError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to generate the executive report.",
      );
      setReportStatus("idle");
    }
  };

  const downloadReport = () => {
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${
      processName
        .trim()
        .replace(/[^a-z0-9]+/gi, "-")
        .toLowerCase() || "process"
    }-executive-report.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setDescription("");
    setStatus("idle");
    setResult(null);
    setError(null);
    setReportStatus("idle");
    setReport("");
    setReportError(null);
    setActiveTab("Analyze");
  };

  return (
    <div className="min-h-screen bg-[#f6f8fc] text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-blue-600 to-violet-600 text-white shadow-lg shadow-blue-200">
              <Route className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight">
                  ProcessPilot AI
                </h1>
                <Badge className="border-0 bg-violet-100 text-violet-700 hover:bg-violet-100">
                  MVP
                </Badge>
              </div>
              <p className="text-xs text-slate-500">
                From process friction to AI impact
              </p>
            </div>
          </div>

          <nav className="hidden items-center rounded-xl bg-slate-100 p-1 md:flex">
            {navItems.map(item => (
              <button
                key={item}
                onClick={() =>
                  (item === "Analyze" || result) && setActiveTab(item as Tab)
                }
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${activeTab === item ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-800"} ${item !== "Analyze" && !result ? "cursor-not-allowed opacity-40" : ""}`}
              >
                {item}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="hidden gap-1.5 rounded-full px-3 py-1.5 text-slate-600 sm:flex"
            >
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" /> Secure
              workspace
            </Badge>
            {(description || result) && (
              <Button
                variant="ghost"
                size="icon"
                onClick={reset}
                className="rounded-xl"
                title="Start over"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8 lg:px-8 lg:py-10">
        <div className="mb-8 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-3 md:p-6">
          <Step
            number="1"
            title="Describe the process"
            subtitle="Share the current workflow"
            active={activeTab === "Analyze"}
            complete={!!result}
          />
          <Step
            number="2"
            title="Discover opportunities"
            subtitle="Find friction and AI use cases"
            active={activeTab === "Insights"}
            complete={activeTab === "Roadmap"}
          />
          <Step
            number="3"
            title="Build the roadmap"
            subtitle="Prioritize value and execution"
            active={activeTab === "Roadmap"}
            complete={false}
          />
        </div>

        <AnimatePresence mode="wait">
          {activeTab === "Analyze" && (
            <motion.div
              key="analyze"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="grid gap-6 lg:grid-cols-[1.45fr_.75fr]"
            >
              <Card className="rounded-3xl border-slate-200 shadow-sm">
                <CardHeader className="border-b border-slate-100 p-6 lg:p-8">
                  <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-2xl tracking-tight">
                    What process should we improve?
                  </CardTitle>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                    Describe the steps, people, tools, approvals, delays, and
                    repetitive work. ProcessPilot will turn your description
                    into actionable AI opportunities.
                  </p>
                </CardHeader>
                <CardContent className="space-y-6 p-6 lg:p-8">
                  <div className="space-y-2">
                    <Label htmlFor="processName">Process name</Label>
                    <Input
                      id="processName"
                      value={processName}
                      onChange={e => setProcessName(e.target.value)}
                      className="h-11 rounded-xl border-slate-200"
                      placeholder="e.g. Employee onboarding"
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <Label htmlFor="description">
                        Current process description
                      </Label>
                      <button
                        onClick={() => {
                          setDescription(exampleProcess);
                          setProcessName("Customer Support Escalation");
                        }}
                        className="text-xs font-semibold text-blue-600 hover:text-blue-700"
                      >
                        Use sample process
                      </button>
                    </div>
                    <Textarea
                      id="description"
                      value={description}
                      onChange={e => setDescription(e.target.value)}
                      placeholder="Example: A customer sends a request by email. An employee copies the data into Excel, asks a manager for approval, then sends a status update manually..."
                      className="min-h-57.5 resize-none rounded-2xl border-slate-200 p-4 leading-6 focus-visible:ring-blue-500"
                    />
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span>
                        Tip: More operational detail produces better
                        recommendations.
                      </span>
                      <span>{description.length} characters</span>
                    </div>
                  </div>

                  <div className="grid gap-4 border-t border-slate-100 pt-6 sm:grid-cols-3">
                    <div className="space-y-2">
                      <Label htmlFor="volume">Monthly cases</Label>
                      <Input
                        id="volume"
                        type="number"
                        min="1"
                        value={volume}
                        onChange={e => setVolume(Number(e.target.value))}
                        className="h-11 rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="minutes">Minutes per case</Label>
                      <Input
                        id="minutes"
                        type="number"
                        min="1"
                        value={minutes}
                        onChange={e => setMinutes(Number(e.target.value))}
                        className="h-11 rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="cost">Hourly cost ($)</Label>
                      <Input
                        id="cost"
                        type="number"
                        min="1"
                        value={hourlyCost}
                        onChange={e => setHourlyCost(Number(e.target.value))}
                        className="h-11 rounded-xl"
                      />
                    </div>
                  </div>

                  <Button
                    onClick={analyze}
                    disabled={
                      description.trim().length < 20 ||
                      processName.trim().length < 2 ||
                      status === "loading"
                    }
                    className="h-12 w-full rounded-xl bg-blue-600 text-base font-semibold shadow-lg shadow-blue-100 hover:bg-blue-700"
                  >
                    {status === "loading" ? (
                      <>
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        Analyzing process...
                      </>
                    ) : (
                      <>
                        <WandSparkles className="mr-2 h-5 w-5" />
                        Analyze with AI
                      </>
                    )}
                  </Button>
                  {error && (
                    <div
                      role="alert"
                      className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
                    >
                      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <Card className="overflow-hidden rounded-3xl border-0 bg-linear-to-br from-slate-950 via-blue-950 to-violet-950 text-white shadow-xl">
                  <CardContent className="p-6 lg:p-7">
                    <div className="mb-8 flex items-start justify-between">
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15">
                        <Bot className="h-5 w-5 text-blue-200" />
                      </div>
                      <Badge className="border border-white/10 bg-white/10 text-blue-100 hover:bg-white/10">
                        AI transformation scout
                      </Badge>
                    </div>
                    <h3 className="text-xl font-bold">
                      Turn hidden friction into measurable value.
                    </h3>
                    <p className="mt-3 text-sm leading-6 text-blue-100/75">
                      ProcessPilot connects operational pain points with
                      practical automation, Copilot, and Azure AI
                      recommendations.
                    </p>
                    <div className="mt-7 space-y-3">
                      {[
                        "Detect bottlenecks",
                        "Recommend AI solutions",
                        "Estimate business impact",
                      ].map(text => (
                        <div
                          key={text}
                          className="flex items-center gap-3 text-sm text-blue-50"
                        >
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />{" "}
                          {text}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card className="rounded-3xl border-slate-200 shadow-sm">
                  <CardContent className="p-6">
                    <div className="mb-5 flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                        <Lightbulb className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-bold">Best input checklist</p>
                        <p className="text-xs text-slate-500">
                          Mention these for stronger analysis
                        </p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {[
                        "Who performs each step?",
                        "Where do delays happen?",
                        "Which tools are used?",
                        "What is copied or repeated?",
                      ].map((item, index) => (
                        <div
                          key={item}
                          className="flex items-center gap-3 text-sm text-slate-600"
                        >
                          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-500">
                            {index + 1}
                          </span>
                          {item}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </motion.div>
          )}

          {activeTab === "Insights" && result && (
            <motion.div
              key="insights"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-6"
            >
              <div className="flex flex-col justify-between gap-4 rounded-3xl bg-linear-to-r from-blue-700 to-violet-700 p-6 text-white shadow-xl shadow-blue-100 md:flex-row md:items-center lg:p-8">
                <div>
                  <Badge className="mb-3 border border-white/15 bg-white/10 text-blue-50 hover:bg-white/10">
                    Analysis complete
                  </Badge>
                  <h2 className="text-2xl font-bold tracking-tight lg:text-3xl">
                    {processName || "Process analysis"}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm text-blue-100">
                    We identified three high-value opportunities to reduce
                    repetitive work and accelerate handoffs.
                  </p>
                </div>
                <div className="rounded-2xl bg-white/10 px-6 py-4 text-center ring-1 ring-white/15">
                  <p className="text-xs font-semibold uppercase tracking-wider text-blue-200">
                    Automation potential
                  </p>
                  <p className="mt-1 text-4xl font-bold">{result.score}%</p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  icon={Route}
                  label="Process steps"
                  value={result.steps}
                  detail="Detected in current workflow"
                  tone="blue"
                />
                <MetricCard
                  icon={Users}
                  label="Manual tasks"
                  value={result.manualTasks}
                  detail="Strong automation candidates"
                  tone="amber"
                />
                <MetricCard
                  icon={Clock3}
                  label="Hours saved"
                  value={`${Math.round(result.hoursSaved)}/mo`}
                  detail={`Estimated at ${result.score}% reduction`}
                  tone="violet"
                />
                <MetricCard
                  icon={Coins}
                  label="Annual value"
                  value={`$${Math.round(result.annualValue).toLocaleString()}`}
                  detail="Productivity value estimate"
                  tone="emerald"
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-[1fr_1.25fr]">
                <Card className="rounded-3xl border-slate-200 shadow-sm">
                  <CardHeader className="p-6 pb-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                        <TriangleAlert className="h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">
                          Process bottlenecks
                        </CardTitle>
                        <p className="text-xs text-slate-500">
                          Where time and effort are being lost
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 p-6 pt-3">
                    {result.bottlenecks.map((item, index) => (
                      <motion.div
                        key={item.title}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.08 }}
                        className="rounded-2xl border border-slate-200 p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="font-bold text-slate-800">
                            {item.title}
                          </p>
                          <Badge
                            className={`${item.severity.includes("High") ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"} border-0 hover:bg-inherit`}
                          >
                            {item.severity}
                          </Badge>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-500">
                          {item.detail}
                        </p>
                      </motion.div>
                    ))}
                  </CardContent>
                </Card>

                <Card className="rounded-3xl border-slate-200 shadow-sm">
                  <CardHeader className="p-6 pb-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                        <Zap className="h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">
                          Recommended AI solutions
                        </CardTitle>
                        <p className="text-xs text-slate-500">
                          Prioritized for practical implementation
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 p-6 pt-3">
                    {result.recommendations.map((item, index) => {
                      const Icon = item.icon;
                      return (
                        <motion.div
                          key={item.name}
                          initial={{ opacity: 0, x: 8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.08 }}
                          className="group rounded-2xl border border-slate-200 p-4 transition hover:border-blue-200 hover:bg-blue-50/30"
                        >
                          <div className="flex gap-4">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                              <Icon className="h-5 w-5" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="font-bold text-slate-800">
                                  {item.name}
                                </p>
                                <Badge variant="outline" className="text-xs">
                                  {item.effort} effort
                                </Badge>
                              </div>
                              <p className="mt-1 text-xs font-semibold text-blue-600">
                                {item.technology}
                              </p>
                              <p className="mt-2 text-sm leading-6 text-slate-500">
                                {item.impact}
                              </p>
                            </div>
                          </div>
                        </motion.div>
                      );
                    })}
                  </CardContent>
                </Card>
              </div>

              <Card className="rounded-3xl border-slate-200 shadow-sm">
                <CardContent className="grid gap-6 p-6 md:grid-cols-[1fr_1.2fr] md:p-8">
                  <div>
                    <div className="mb-3 flex items-center gap-2 text-sm font-bold text-emerald-700">
                      <TrendingUp className="h-4 w-4" />
                      Estimated business case
                    </div>
                    <h3 className="text-2xl font-bold tracking-tight">
                      Save {Math.round(result.hoursSaved)} hours every month
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-500">
                      Based on {volume.toLocaleString()} monthly cases,{" "}
                      {minutes} minutes per case, and an estimated{" "}
                      {result.score}% time reduction.
                    </p>
                  </div>
                  <div className="space-y-4 rounded-2xl bg-slate-50 p-5">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">
                        Current monthly effort
                      </span>
                      <span className="font-bold">
                        {Math.round(result.currentHours).toLocaleString()} hours
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">
                        Estimated time reduction
                      </span>
                      <span className="font-bold text-emerald-600">
                        {result.score}%
                      </span>
                    </div>
                    <Progress value={result.score} className="h-2.5" />
                    <div className="flex justify-between border-t border-slate-200 pt-4">
                      <span className="font-semibold text-slate-600">
                        Monthly productivity value
                      </span>
                      <span className="text-xl font-bold text-slate-900">
                        ${Math.round(result.monthlyValue).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="flex justify-end">
                <Button
                  onClick={() => setActiveTab("Roadmap")}
                  className="h-12 rounded-xl bg-slate-950 px-6 hover:bg-slate-800"
                >
                  Build implementation roadmap{" "}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </motion.div>
          )}

          {activeTab === "Roadmap" && result && (
            <motion.div
              key="roadmap"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              <div className="max-w-3xl">
                <Badge className="mb-3 border-0 bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
                  Recommended roadmap
                </Badge>
                <h2 className="text-3xl font-bold tracking-tight">
                  Start small, prove value, then scale.
                </h2>
                <p className="mt-3 text-slate-500">
                  A practical three-phase plan designed for a low-risk pilot and
                  measurable business impact.
                </p>
              </div>

              <div className="grid gap-5 lg:grid-cols-3">
                {[
                  {
                    phase: "Phase 1",
                    time: "Week 1",
                    title: "Discover & baseline",
                    icon: Target,
                    color: "blue",
                    items: [
                      "Validate the current process",
                      "Confirm baseline metrics",
                      "Select one pilot scenario",
                    ],
                  },
                  {
                    phase: "Phase 2",
                    time: "Weeks 2–3",
                    title: "Build the pilot",
                    icon: Play,
                    color: "violet",
                    items: [
                      "Configure the intake agent",
                      "Automate one core workflow",
                      "Test with sample cases",
                    ],
                  },
                  {
                    phase: "Phase 3",
                    time: "Week 4",
                    title: "Measure & scale",
                    icon: Gauge,
                    color: "emerald",
                    items: [
                      "Compare time and quality",
                      "Collect employee feedback",
                      "Prepare the scale decision",
                    ],
                  },
                ].map((phase, index) => {
                  const Icon = phase.icon;
                  const colors: Record<string, string> = {
                    blue: "bg-blue-600",
                    violet: "bg-violet-600",
                    emerald: "bg-emerald-600",
                  };
                  return (
                    <motion.div
                      key={phase.phase}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.1 }}
                    >
                      <Card className="h-full rounded-3xl border-slate-200 shadow-sm">
                        <CardContent className="p-6">
                          <div className="mb-6 flex items-center justify-between">
                            <div
                              className={`flex h-11 w-11 items-center justify-center rounded-2xl text-white ${colors[phase.color]}`}
                            >
                              <Icon className="h-5 w-5" />
                            </div>
                            <Badge variant="outline">{phase.time}</Badge>
                          </div>
                          <p className="text-xs font-bold uppercase tracking-widest text-slate-400">
                            {phase.phase}
                          </p>
                          <h3 className="mt-1 text-xl font-bold">
                            {phase.title}
                          </h3>
                          <div className="mt-5 space-y-3">
                            {phase.items.map(item => (
                              <div
                                key={item}
                                className="flex items-center gap-3 text-sm text-slate-600"
                              >
                                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                                {item}
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  );
                })}
              </div>

              <Card className="rounded-3xl border-0 bg-slate-950 text-white shadow-xl">
                <CardContent className="grid gap-6 p-6 md:grid-cols-[1fr_auto] md:items-center md:p-8">
                  <div>
                    <div className="mb-3 flex items-center gap-2 text-sm font-bold text-blue-300">
                      <FileText className="h-4 w-4" />
                      Executive-ready recommendation
                    </div>
                    <h3 className="text-2xl font-bold">
                      Pilot the Case Intake Agent first.
                    </h3>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                      It targets a high-impact manual step, has clear success
                      metrics, and creates structured data that enables the
                      remaining automations.
                    </p>
                  </div>
                  <Button
                    onClick={generateReport}
                    disabled={reportStatus === "loading"}
                    className="h-12 rounded-xl bg-white px-6 text-slate-950 hover:bg-blue-50"
                  >
                    {reportStatus === "loading" ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Generating report...
                      </>
                    ) : (
                      <>
                        {report
                          ? "Regenerate report"
                          : "Generate executive report"}
                        <ChevronRight className="ml-2 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              {reportError && (
                <div
                  role="alert"
                  className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
                >
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{reportError}</span>
                </div>
              )}

              {report && (
                <Card className="rounded-3xl border-slate-200 shadow-sm">
                  <CardHeader className="flex-row items-center justify-between gap-4 border-b border-slate-100 p-6">
                    <div>
                      <CardTitle className="text-xl">
                        Executive report
                      </CardTitle>
                      <p className="mt-1 text-sm text-slate-500">
                        Generated from the saved process analysis
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={downloadReport}
                      title="Download Markdown report"
                      aria-label="Download Markdown report"
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </CardHeader>
                  <CardContent className="p-6 md:p-8">
                    <pre className="overflow-x-auto whitespace-pre-wrap font-sans text-sm leading-7 text-slate-700">
                      {report}
                    </pre>
                  </CardContent>
                </Card>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer className="mx-auto max-w-7xl px-5 pb-8 pt-4 text-center text-xs text-slate-400 lg:px-8">
        ProcessPilot AI prototype • ROI values are directional estimates for
        pilot planning
      </footer>
    </div>
  );
}
