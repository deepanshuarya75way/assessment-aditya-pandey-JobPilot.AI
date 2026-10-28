"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchAPI } from "@/lib/api";
import Link from "next/link";

function safeEvidenceUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;

  try {
    const parsedUrl = new URL(value);

    if (
      (parsedUrl.protocol === "https:" ||
        parsedUrl.protocol === "http:") &&
      parsedUrl.hostname
    ) {
      return parsedUrl.href;
    }
  } catch {
    // Ignore invalid URLs.
  }

  return null;
}

function renderEvidenceItems(
  items: any,
  emptyMessage: string,
  urlField = "url",
  linkLabel = "Open source ↗"
) {
  if (!Array.isArray(items) || items.length === 0) {
    return (
      <p className="text-sm text-slate-600">
        {emptyMessage}
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((item: any, index: number) => {
        const title =
          item.label ||
          item.title ||
          item.matched_phrase ||
          item.kind ||
          "Evidence";

        const url = safeEvidenceUrl(item[urlField]);

        return (
          <li
            key={`${title}-${index}`}
            className="rounded-xl border border-slate-200 p-4"
          >
            <p className="font-semibold text-slate-900">
              {title}
            </p>

            {item.source && (
              <p className="mt-1 text-xs text-slate-500">
                Source: {item.source}
              </p>
            )}

            {item.summary && (
              <p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700">
                {item.summary}
              </p>
            )}

            {item.source_title && (
              <p className="mt-2 text-sm text-slate-700">
                Source result: {item.source_title}
              </p>
            )}

            {item.source_summary && (
              <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-600">
                {item.source_summary}
              </p>
            )}

            {typeof item.confidence === "number" && (
              <p className="mt-2 text-xs text-slate-500">
                Source confidence:{" "}
                {Math.round(
                  item.confidence <= 1
                    ? item.confidence * 100
                    : item.confidence
                )}
                %
              </p>
            )}

            {url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block break-all text-sm font-semibold text-indigo-700 underline"
              >
                {linkLabel}
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();

  const source = params.source as string;
  const id = params.id as string;

  const [job, setJob] = useState<any>(null);
  const [resumeText, setResumeText] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [alreadyTracked, setAlreadyTracked] = useState(false);

  useEffect(() => {
    fetchAPI(`/jobs/detail/${source}/${id}`)
      .then((data) => {
        setJob(data.job);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });

    // Check if job is already in Kanban tracker.
    fetchAPI("/jobs/applications")
      .then((data) => {
        const apps = data.applications || [];

        const exists = apps.some(
          (a: any) =>
            a.job?.external_id === id ||
            a.external_id === id
        );

        setAlreadyTracked(exists);
      })
      .catch(() => {});

    const savedResume = sessionStorage.getItem("current_resume");

    if (savedResume) {
      setResumeText(savedResume);
    }
  }, [source, id]);

  const handleRunAnalysis = async () => {
    if (!resumeText.trim()) {
      alert("Please provide resume text to run ATS analysis.");
      return;
    }

    setAnalyzing(true);
    setError(null);

    try {
      const data = await fetchAPI(
        `/jobs/detail/${source}/${id}/analyze`,
        {
          method: "POST",
          body: JSON.stringify({
            resume_text: resumeText,
          }),
        }
      );

      setAnalysisResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerateApplication = async () => {
    if (!resumeText.trim()) {
      alert("Please provide resume text.");
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      await fetchAPI("/jobs/application", {
        method: "POST",
        body: JSON.stringify({
          source,
          external_id: id,
          resume_text: resumeText,
        }),
      });

      router.push("/applications");
    } catch (err: any) {
      setError(
        `Application generation failed: ${err.message}`
      );
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-slate-50">
        <div className="flex gap-2">
          <div
            className="h-3 w-3 animate-bounce rounded-full bg-slate-800"
            style={{ animationDelay: "0ms" }}
          />
          <div
            className="h-3 w-3 animate-bounce rounded-full bg-slate-600"
            style={{ animationDelay: "150ms" }}
          />
          <div
            className="h-3 w-3 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: "300ms" }}
          />
        </div>

        <p className="mt-4 animate-pulse text-sm font-bold uppercase tracking-widest text-slate-800">
          Fetching Job Details...
        </p>
      </div>
    );
  }

  if (error && !job) {
    return (
      <p className="p-10 font-bold text-red-500">
        Error: {error}
      </p>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      <div className="mx-auto max-w-5xl p-6 pt-10 text-black">
        <div className="mb-8 flex items-center justify-between">
          <Link
            href="/"
            className="group flex items-center gap-2 font-bold text-slate-500 transition-colors hover:text-indigo-600"
          >
            <span className="transform transition-transform group-hover:-translate-x-1">
              &larr;
            </span>
            Back to Search
          </Link>

          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-full border-2 border-slate-200 bg-white px-6 py-2.5 font-bold text-slate-800 shadow-sm transition-all hover:-translate-y-0.5 hover:border-slate-800 hover:shadow-md active:scale-95"
          >
            Original Posting ↗
          </a>
        </div>

        <div className="mb-8 transform rounded-3xl border border-slate-100 bg-white p-10 shadow-xl transition-transform duration-500 hover:-translate-y-1">
          <div className="mb-4 inline-block rounded-full bg-indigo-50 px-4 py-1.5 text-xs font-black uppercase tracking-widest text-indigo-700">
            {job.source}
          </div>

          <h1 className="mb-3 text-4xl font-black text-slate-900">
            {job.title}
          </h1>

          <p className="mb-4 text-2xl font-bold text-slate-600">
            {job.company}
          </p>

          <p className="flex items-center gap-2 text-sm font-medium text-slate-500">
            <span className="rounded-md bg-slate-100 p-1.5">
              📍
            </span>
            {job.location}
          </p>
        </div>

        <div className="relative mb-10 overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-900 to-slate-900 p-10 text-white shadow-2xl">
          <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-indigo-600 opacity-20 blur-3xl" />

          <h2 className="relative z-10 mb-3 text-2xl font-black">
            Run ATS Match & Trust Evaluation
          </h2>

          <p className="relative z-10 mb-6 max-w-2xl font-medium text-indigo-200">
            Analyze this specific posting against your resume
            for keyword match, ATS scores, and company
            credibility before you apply.
          </p>

          <textarea
            placeholder="Paste or update your resume text here..."
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            className="relative z-10 mb-6 h-32 w-full rounded-2xl border-2 border-indigo-500/30 bg-white/10 p-5 text-white backdrop-blur-md transition-all placeholder:text-indigo-300 focus:border-indigo-400 focus:outline-none focus:ring-4 focus:ring-indigo-500/20"
          />

          <div className="relative z-10 flex flex-col gap-4 sm:flex-row">
            <button
              onClick={handleRunAnalysis}
              disabled={analyzing || generating}
              className="flex-1 rounded-xl border border-white/20 bg-white/10 px-6 py-4 font-bold text-white shadow-lg backdrop-blur-sm transition-all hover:-translate-y-1 hover:bg-white/20 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
            >
              {analyzing ? (
                <span className="flex animate-pulse items-center justify-center gap-2">
                  <span className="text-xl">⚙️</span>
                  Analyzing...
                </span>
              ) : (
                "1. Analyze Job Match"
              )}
            </button>

            <button
              onClick={handleGenerateApplication}
              disabled={
                analyzing ||
                generating ||
                !resumeText ||
                alreadyTracked
              }
              className="flex-1 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-6 py-4 font-bold text-white shadow-lg transition-all hover:-translate-y-1 hover:shadow-xl hover:shadow-emerald-500/20 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {alreadyTracked
                ? "✓ Application Already in Tracker"
                : generating
                  ? (
                    <span className="flex animate-pulse items-center justify-center gap-2">
                      <span className="text-xl">✨</span>
                      Crafting...
                    </span>
                  )
                  : "2. Generate AI Application"}
            </button>
          </div>

          {error && (
            <p className="relative z-10 mt-4 inline-block rounded-lg border border-rose-900/50 bg-rose-950/50 p-3 text-sm font-bold text-rose-400">
              {error}
            </p>
          )}
        </div>

        {analysisResult && (
          <div className="mb-10 animate-fade-in-up space-y-8">
            {/* Existing score cards remain unchanged. */}
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <div className="rounded-3xl border border-emerald-100 bg-white p-8 text-center shadow-xl transition-transform duration-300 hover:-translate-y-2">
                <span className="text-xs font-black uppercase tracking-widest text-emerald-600">
                  Overall Score
                </span>

                <p className="mt-4 bg-gradient-to-br from-emerald-400 to-teal-600 bg-clip-text text-6xl font-black text-transparent">
                  {analysisResult.ats_match?.overall_score}%
                </p>
              </div>

              <div className="rounded-3xl border border-blue-100 bg-white p-8 text-center shadow-xl transition-transform duration-300 hover:-translate-y-2">
                <span className="text-xs font-black uppercase tracking-widest text-blue-600">
                  Skill Match
                </span>

                <p className="mt-4 bg-gradient-to-br from-blue-400 to-indigo-600 bg-clip-text text-6xl font-black text-transparent">
                  {analysisResult.ats_match?.skill_score}%
                </p>
              </div>

              <div className="rounded-3xl border border-purple-100 bg-white p-8 text-center shadow-xl transition-transform duration-300 hover:-translate-y-2">
                <span className="text-xs font-black uppercase tracking-widest text-purple-600">
                  Company Trust
                </span>

                <p className="mt-4 bg-gradient-to-br from-purple-400 to-fuchsia-600 bg-clip-text text-6xl font-black text-transparent">
                  {analysisResult.company_trust?.trust_score ?? "N/A"}
                </p>

                <span className="mt-3 inline-block rounded-full bg-purple-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-purple-700">
                  {analysisResult.company_trust?.recommendation}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="rounded-3xl border border-emerald-200 bg-emerald-50/50 p-8 shadow-lg transition-shadow duration-300 hover:shadow-xl">
                <h3 className="mb-6 flex items-center gap-2 font-black text-emerald-900">
                  <span className="text-xl">✅</span>
                  Matched Skills
                </h3>

                <div className="flex flex-wrap gap-2">
                  {analysisResult.ats_match?.matched_skills?.map(
                    (skill: string, index: number) => (
                      <span
                        key={index}
                        className="cursor-default rounded-xl border border-emerald-200 bg-white px-4 py-2 text-sm font-bold text-emerald-800 shadow-sm transition-transform hover:scale-105"
                      >
                        {skill}
                      </span>
                    )
                  )}
                </div>
              </div>

              <div className="rounded-3xl border border-rose-200 bg-rose-50/50 p-8 shadow-lg transition-shadow duration-300 hover:shadow-xl">
                <h3 className="mb-6 flex items-center gap-2 font-black text-rose-900">
                  <span className="text-xl">❌</span>
                  Missing Skills
                </h3>

                <div className="flex flex-wrap gap-2">
                  {analysisResult.ats_match?.missing_skills?.map(
                    (skill: string, index: number) => (
                      <span
                        key={index}
                        className="cursor-default rounded-xl border border-rose-200 bg-white px-4 py-2 text-sm font-bold text-rose-800 shadow-sm transition-transform hover:scale-105"
                      >
                        {skill}
                      </span>
                    )
                  )}
                </div>
              </div>
            </div>

            {analysisResult.company_trust?.red_flags?.length > 0 && (
              <div className="rounded-3xl border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 p-8 shadow-lg">
                <h3 className="mb-4 flex items-center gap-2 font-black text-amber-900">
                  <span className="text-2xl">⚠️</span>
                  Due Diligence Notices
                </h3>

                <ul className="space-y-3">
                  {analysisResult.company_trust.red_flags.map(
                    (flag: string, index: number) => (
                      <li
                        key={index}
                        className="flex items-start gap-3 rounded-xl border border-amber-100 bg-white/50 p-4 font-medium text-amber-900"
                      >
                        <span className="mt-0.5 text-amber-500">
                          •
                        </span>
                        {flag}
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}

            {/* New evidence report. It does not change the trust result. */}
            <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-lg">
              <h3 className="mb-2 text-xl font-black text-slate-900">
                Company Evidence Report
              </h3>

              <p className="mb-6 text-sm text-slate-600">
                Review the information behind the company
                trust result. Missing information is not, by
                itself, proof of fraud. The score and
                recommendation above remain unchanged.
              </p>

              {analysisResult.company_evidence ? (
                <div className="space-y-7">
                  <section>
                    <h4 className="mb-3 font-bold text-slate-900">
                      Available Company Evidence
                    </h4>

                    {renderEvidenceItems(
                      analysisResult.company_evidence.available,
                      "No verified company links were provided by the API.",
                      "url",
                      "Open company page ↗"
                    )}
                  </section>

                  <section>
                    <h4 className="mb-3 font-bold text-rose-900">
                      Risk Indicators
                    </h4>

                    {renderEvidenceItems(
                      analysisResult.company_evidence.risk_signals,
                      "No specific risk phrases were reported in the collected evidence. This does not prove the company is safe.",
                      "source_url",
                      "View source ↗"
                    )}
                  </section>

                  <section>
                    <h4 className="mb-3 font-bold text-slate-900">
                      Public Search Evidence
                    </h4>

                    {renderEvidenceItems(
                      analysisResult.company_evidence.search_results,
                      "No public search results were returned by the API."
                    )}
                  </section>

                  <section>
                    <h4 className="mb-3 font-bold text-amber-900">
                      Unavailable Evidence
                    </h4>

                    {renderEvidenceItems(
                      analysisResult.company_evidence.unavailable,
                      "The API did not report any unavailable evidence."
                    )}
                  </section>
                </div>
              ) : (
                <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
                  Evidence details were not included in the
                  API response. Your existing company trust
                  score and recommendation are still shown
                  above.
                </p>
              )}
            </div>
          </div>
        )}

        <div className="rounded-3xl border border-slate-100 bg-white p-10 shadow-xl">
          <h2 className="mb-6 text-2xl font-black text-slate-900">
            Job Description
          </h2>

          <div className="whitespace-pre-wrap text-sm font-medium leading-relaxed text-slate-700 md:text-base">
            {job.description || "No full description provided."}
          </div>
        </div>
      </div>
    </div>
  );
}