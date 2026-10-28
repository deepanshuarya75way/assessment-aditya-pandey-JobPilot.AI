"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { API_URL, fetchAPI } from "@/lib/api";
import Link from "next/link";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<{ name: string } | null>(null);

  const [query, setQuery] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [jobs, setJobs] = useState<any[]>([]);

  useEffect(() => {
    // 1. Fetch user authentication
    fetchAPI("/auth/me")
      .then((data) => setUser(data))
      .catch(() => {
        localStorage.removeItem("token");
        router.push("/login");
      });

    // 2. Fetch the permanently saved resume details from the database
    fetchAPI("/profile/details")
      .then((data) => {
        if (data.resume_text) {
          setResumeText(data.resume_text);
          sessionStorage.setItem("current_resume", data.resume_text);
        } else {
          const savedResume = sessionStorage.getItem("current_resume");
          if (savedResume) setResumeText(savedResume);
        }
      })
      .catch((err) => console.error("Failed to fetch profile details:", err));

    // NEW: 3. Restore previous search state if coming back to this page
    const savedQuery = sessionStorage.getItem("saved_search_query");
    if (savedQuery) setQuery(savedQuery);

    const savedJobs = sessionStorage.getItem("saved_search_results");
    if (savedJobs) {
      try {
        setJobs(JSON.parse(savedJobs));
      } catch (e) {
        console.error("Failed to parse saved jobs");
      }
    }
      
  }, [router]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/profile/upload-resume`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const textToDisplay = data.skills || data.resume_text || "";
        setResumeText(textToDisplay);
        sessionStorage.setItem("current_resume", textToDisplay);
        alert("✅ Resume parsed successfully!");
      } else {
        alert(`❌ Error: ${data.detail || "Upload failed"}`);
      }
    } catch (error) {
      alert("❌ Failed to upload resume.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleSaveDetails = async () => {
    setIsSaving(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/profile/update-details`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ details: resumeText }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        sessionStorage.setItem("current_resume", resumeText);
        alert("✅ Details saved successfully!");
      } else {
        alert(`❌ Error: ${data.detail || "Failed to save"}`);
      }
    } catch (error) {
      alert("❌ Failed to save details.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    // Save current state to session storage
    sessionStorage.setItem("current_resume", resumeText);
    sessionStorage.setItem("saved_search_query", query);

    try {
      const data = await fetchAPI("/jobs/search", {
        method: "POST",
        body: JSON.stringify({ query, resume_text: resumeText }),
      });
      const fetchedJobs = data.jobs || [];
      setJobs(fetchedJobs);
      
      // NEW: Save the actual job results so they survive a back-button press
      sessionStorage.setItem("saved_search_results", JSON.stringify(fetchedJobs));
      
    } catch (err: any) {
      alert(`Search failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    // Clear the saved search when logging out so the next person doesn't see it
    sessionStorage.removeItem("saved_search_query");
    sessionStorage.removeItem("saved_search_results");
    sessionStorage.clear();
    router.replace("/login");
  };

  if (!user) return (
    <div className="flex justify-center items-center h-screen bg-slate-50">
       <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 pb-16">
      <div className="bg-gradient-to-r from-slate-900 to-indigo-900 text-white pt-8 pb-32 px-6 rounded-b-[3rem] shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10 mix-blend-overlay"></div>
        <div className="max-w-7xl mx-auto relative z-10 flex flex-col md:flex-row justify-between items-center gap-6">
          <div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-2">
              Welcome back, <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">{user.name}</span>
            </h1>
            <p className="text-indigo-200 font-medium text-lg">Let's find your next big opportunity.</p>
          </div>
          
          <div className="flex flex-wrap gap-4">
            <Link href="/extension" className="bg-white/10 backdrop-blur-md border border-white/20 text-white px-6 py-2.5 rounded-full font-bold shadow-lg hover:bg-white/20 hover:scale-105 active:scale-95 transition-all flex items-center gap-2">
              <span>🧩</span> Extension
            </Link>
            <Link href="/applications" className="bg-white/10 backdrop-blur-md border border-white/20 text-white px-6 py-2.5 rounded-full font-bold shadow-lg hover:bg-white/20 hover:scale-105 active:scale-95 transition-all flex items-center gap-2">
              <span>📋</span> Tracker
            </Link>
            <button onClick={logout} className="bg-rose-500/10 border border-rose-500/30 text-rose-300 px-6 py-2.5 rounded-full font-bold shadow-lg hover:bg-rose-500 hover:text-white hover:scale-105 active:scale-95 transition-all">
              Logout
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 -mt-20 relative z-20">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          <div className="lg:col-span-1">
            <div className="bg-white rounded-3xl p-8 shadow-xl border border-slate-100 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300">
              <h2 className="text-2xl font-black mb-3 text-slate-900">Profile Context</h2>
              <p className="text-sm text-slate-500 mb-6 font-medium">
                Upload your resume PDF. Our AI will extract your details here and save your full background to the database for extension analysis.
              </p>
              
              <input type="file" id="resumeUpload" accept="application/pdf" className="hidden" onChange={handleFileUpload} />
              <button
                type="button"
                onClick={() => document.getElementById("resumeUpload")?.click()}
                disabled={uploading}
                className="w-full mb-6 bg-gradient-to-r from-indigo-50 to-purple-50 text-indigo-700 border-2 border-indigo-200 border-dashed px-4 py-4 rounded-2xl font-black tracking-wide hover:bg-indigo-100 hover:border-indigo-300 hover:scale-[1.02] active:scale-95 transition-all disabled:opacity-70 flex justify-center items-center"
              >
                {uploading ? <span className="animate-pulse">⏳ Parsing PDF...</span> : <span>📄 Upload Resume (PDF)</span>}
              </button>

              <label className="block text-sm font-black text-slate-900 mb-2 uppercase tracking-wider">
                Extracted Details
              </label>
              <textarea
                placeholder="Upload a PDF to auto-extract, or type details manually..."
                className="w-full p-4 border-2 border-slate-200 rounded-2xl h-48 bg-slate-50 text-slate-700 font-medium focus:ring-4 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white transition-all resize-none mb-2"
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
              />
              <p className="text-xs text-slate-400 font-medium mb-6">
                These details directly influence your AI job search relevance.
              </p>

              <button
                onClick={handleSaveDetails}
                disabled={isSaving || !resumeText}
                className="w-full bg-indigo-600 text-white px-4 py-3.5 rounded-xl font-black shadow-lg hover:shadow-xl hover:bg-indigo-700 hover:-translate-y-0.5 active:scale-95 transition-all disabled:bg-slate-300 disabled:cursor-not-allowed"
              >
                {isSaving ? <span className="animate-pulse">Saving...</span> : "Save Details"}
              </button>
            </div>
          </div>

          <div className="lg:col-span-2">
            <form onSubmit={handleSearch} className="bg-white rounded-3xl p-8 shadow-xl border border-slate-100 mb-8 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300">
              <h2 className="text-3xl font-black mb-2 text-slate-900">Discover Jobs</h2>
              <p className="text-slate-500 mb-8 font-medium">Search for roles across India using Deep Semantic Matching.</p>
              
              <div className="flex flex-col sm:flex-row gap-4">
                <input
                  type="text"
                  placeholder="e.g., Senior Backend Engineer in Python..."
                  required
                  className="flex-1 p-4 border-2 border-slate-200 rounded-2xl bg-slate-50 text-lg font-medium focus:ring-4 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white transition-all outline-none"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <button
                  disabled={loading}
                  type="submit"
                  className="bg-slate-900 text-white px-10 py-4 rounded-2xl font-black tracking-wide shadow-lg hover:shadow-xl hover:bg-indigo-600 hover:-translate-y-0.5 active:scale-95 disabled:bg-slate-300 disabled:cursor-not-allowed transition-all whitespace-nowrap"
                >
                  {loading ? <span className="animate-pulse">Scanning...</span> : "Search"}
                </button>
              </div>
            </form>

            <div className="space-y-4">
              {jobs.length > 0 && (
                <div className="flex items-center gap-3 mb-6">
                  <h3 className="text-xl font-black text-slate-900">Live Listings</h3>
                  <span className="bg-indigo-100 text-indigo-800 text-sm font-bold px-3 py-1 rounded-full">{jobs.length} Matches</span>
                </div>
              )}

              {jobs.length === 0 && !loading && (
                <div className="text-center py-20 bg-white/50 backdrop-blur rounded-3xl border-2 border-dashed border-slate-300">
                  <div className="text-6xl mb-4 opacity-50">📡</div>
                  <p className="text-slate-700 font-bold text-xl">No jobs passed the AI relevance filter.</p>
                  <p className="text-slate-500 font-medium mt-2">Try a broader search query or update your profile details.</p>
                </div>
              )}

              {loading && (
                 <div className="space-y-4">
                    {[1,2,3].map(i => (
                       <div key={i} className="h-32 bg-slate-200 rounded-2xl animate-pulse"></div>
                    ))}
                 </div>
              )}

              {!loading && jobs.map((item, idx) => {
                const job = item.job || item;
                return (
                  <div key={idx} className="group bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-xl hover:-translate-y-1 hover:border-indigo-200 transition-all duration-300 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-6">
                    <div>
                      <h4 className="text-2xl font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">{job.title}</h4>
                      <p className="text-lg font-bold text-slate-600 mt-1">{job.company}</p>
                      <div className="flex flex-wrap items-center gap-3 mt-3">
                        <span className="bg-slate-100 text-slate-700 px-3 py-1 rounded-md text-sm font-bold">📍 {job.location}</span> 
                        <span className="bg-indigo-50 text-indigo-700 uppercase tracking-widest px-3 py-1 rounded-md text-xs font-black">{job.source}</span>
                      </div>
                    </div>

                    <Link
                      href={`/jobs/${job.source}/${job.external_id}`}
                      className="bg-white text-indigo-600 border-2 border-indigo-100 px-8 py-3 rounded-full font-black shadow-sm group-hover:bg-indigo-600 group-hover:text-white group-hover:border-indigo-600 group-hover:shadow-lg active:scale-95 transition-all text-center whitespace-nowrap"
                    >
                      Analyze Role &rarr;
                    </Link>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}