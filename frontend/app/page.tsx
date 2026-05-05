"use client";

import Link from "next/link";
import {
  Globe, Zap, ArrowRight, CheckCircle2, BarChart2, Search,
  FileText, ShieldCheck, TrendingUp, Bot, Target, Layers,
  ChevronRight, Star, Clock, Users,
} from "lucide-react";

// ── Nav ───────────────────────────────────────────────────────────────────────
function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-gray-950/80 backdrop-blur-lg">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-atlas-500 rounded-lg flex items-center justify-center shadow-lg shadow-atlas-500/30">
            <Globe size={16} className="text-white" />
          </div>
          <span className="text-white font-bold text-lg tracking-tight">Atlas</span>
          <span className="hidden sm:block text-gray-500 text-xs border border-gray-800 rounded px-1.5 py-0.5">SEO & GEO Agent</span>
        </div>

        {/* Links */}
        <div className="hidden md:flex items-center gap-7 text-sm text-gray-400">
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-white transition-colors">How it works</a>
          <a href="#audit" className="hover:text-white transition-colors">Free Audit</a>
        </div>

        {/* CTA */}
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-gray-400 hover:text-white transition-colors hidden sm:block">
            Sign in
          </Link>
          <Link
            href="/register"
            className="bg-atlas-500 hover:bg-atlas-600 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors shadow-lg shadow-atlas-500/20"
          >
            Get Started Free
          </Link>
        </div>
      </div>
    </nav>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center px-6 pt-16 overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-atlas-500/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/4 w-[300px] h-[300px] bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      {/* Grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative max-w-5xl mx-auto text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 bg-atlas-500/10 border border-atlas-500/30 text-atlas-300 text-xs font-medium px-3.5 py-1.5 rounded-full mb-8">
          <Zap size={12} />
          AI-Powered Autonomous SEO Agent
        </div>

        {/* Headline */}
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-white leading-[1.08] tracking-tight mb-6">
          Your SEO Agent That{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-atlas-500 to-purple-400">
            Actually Does the Work
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-gray-400 text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
          Atlas crawls your entire site, researches 1000+ keywords, scores your AI
          visibility, and builds a prioritised action plan — then waits for your
          approval before touching anything.
        </p>

        {/* CTA buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <Link
            href="/register"
            className="group bg-atlas-500 hover:bg-atlas-600 text-white font-semibold px-8 py-4 rounded-xl text-base transition-all shadow-xl shadow-atlas-500/25 flex items-center gap-2"
          >
            Start Analysing My Site
            <ArrowRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
          </Link>
          <Link
            href="/audit"
            className="text-gray-300 hover:text-white border border-gray-700 hover:border-gray-500 px-8 py-4 rounded-xl text-base transition-all flex items-center gap-2"
          >
            <Search size={16} />
            Free Quick Audit
          </Link>
        </div>

        {/* Social proof bar */}
        <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-gray-500">
          {[
            { icon: <ShieldCheck size={14} className="text-green-400" />, text: "No changes without approval" },
            { icon: <Clock size={14} className="text-atlas-400" />, text: "Full audit in under 5 minutes" },
            { icon: <Star size={14} className="text-yellow-400" />, text: "Works on any website" },
          ].map(({ icon, text }) => (
            <div key={text} className="flex items-center gap-1.5">
              {icon}
              <span>{text}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function Stats() {
  return (
    <section className="border-y border-gray-800 bg-gray-900/40 py-12 px-6">
      <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
        {[
          { value: "500+",  label: "Pages crawled per audit" },
          { value: "1000+", label: "Keywords researched" },
          { value: "6",     label: "SEO modules running" },
          { value: "0",     label: "Changes without approval" },
        ].map(({ value, label }) => (
          <div key={label}>
            <p className="text-3xl font-extrabold text-white mb-1">{value}</p>
            <p className="text-gray-500 text-sm">{label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── How it works ──────────────────────────────────────────────────────────────
function HowItWorks() {
  const steps = [
    {
      number: "01",
      icon: <Globe size={22} className="text-atlas-400" />,
      title: "Enter Your Website URL",
      desc: "Just paste your domain. No plugins to install, no API keys to configure. Atlas handles everything else.",
    },
    {
      number: "02",
      icon: <Search size={22} className="text-atlas-400" />,
      title: "AI Audits Everything",
      desc: "Atlas crawls every page, researches keywords, analyses competitors, and scores your AI visibility — all in minutes.",
    },
    {
      number: "03",
      icon: <FileText size={22} className="text-atlas-400" />,
      title: "Get Your Action Plan",
      desc: "Every issue is prioritised by urgency and impact. You get a clear, ranked list of exactly what to fix and why.",
    },
    {
      number: "04",
      icon: <CheckCircle2 size={22} className="text-atlas-400" />,
      title: "Approve & Execute",
      desc: "Review each recommended change before it goes live. One click to approve, one click to reject — you're always in control.",
    },
  ];

  return (
    <section id="how-it-works" className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <p className="text-atlas-400 text-sm font-semibold uppercase tracking-wider mb-3">How it works</p>
          <h2 className="text-4xl font-bold text-white">From URL to Action Plan in Minutes</h2>
          <p className="text-gray-400 mt-4 max-w-xl mx-auto">
            No agencies. No manual analysis. No guesswork. Just a clear plan backed by AI.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {steps.map((step, i) => (
            <div key={step.number} className="relative">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-[calc(100%+0px)] w-6 h-px bg-gray-800 z-10" />
              )}
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 h-full hover:border-atlas-500/30 transition-colors">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-xs font-bold text-atlas-500/50 font-mono">{step.number}</span>
                  <div className="w-9 h-9 bg-atlas-500/10 rounded-xl flex items-center justify-center">
                    {step.icon}
                  </div>
                </div>
                <h3 className="text-white font-semibold mb-2">{step.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Features ──────────────────────────────────────────────────────────────────
function Features() {
  const features = [
    {
      icon: <Search size={20} className="text-atlas-400" />,
      title: "Full Site Crawl",
      desc: "Crawls up to 500+ pages per audit. Finds broken links, missing tags, slow pages, thin content and 15+ other SEO issues automatically.",
    },
    {
      icon: <Target size={20} className="text-purple-400" />,
      title: "Keyword Intelligence",
      desc: "Auto-generates 1000+ keyword variations from your site content. Classified by intent (informational, commercial, transactional) and clustered by topic.",
    },
    {
      icon: <Bot size={20} className="text-yellow-400" />,
      title: "GEO Scoring",
      desc: "Scores how visible you are to AI models like ChatGPT and Gemini. Identifies exactly which pages need structured data and better E-E-A-T signals.",
    },
    {
      icon: <BarChart2 size={20} className="text-green-400" />,
      title: "Competitor Analysis",
      desc: "Analyses what your top competitors are doing right. Reveals content gaps and ranking opportunities you're currently missing.",
    },
    {
      icon: <Layers size={20} className="text-orange-400" />,
      title: "Approval Queue",
      desc: "Every recommended change appears in a queue for you to review. Approve individually or in bulk. Nothing goes live until you say so.",
    },
    {
      icon: <FileText size={20} className="text-blue-400" />,
      title: "Content Generation",
      desc: "Generate SEO-optimised blog posts, local landing pages, and service pages. Written to match your brand voice and target keywords.",
    },
    {
      icon: <TrendingUp size={20} className="text-red-400" />,
      title: "Performance Analytics",
      desc: "Connect Google Search Console to track clicks, impressions, and average position over time. See exactly what's trending.",
    },
    {
      icon: <ShieldCheck size={20} className="text-teal-400" />,
      title: "Runs Locally",
      desc: "Install on your own machine. Your data never leaves your server. No third-party API keys required — everything runs on-device.",
    },
  ];

  return (
    <section id="features" className="py-24 px-6 bg-gray-900/20">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <p className="text-atlas-400 text-sm font-semibold uppercase tracking-wider mb-3">Features</p>
          <h2 className="text-4xl font-bold text-white">Everything You Need to Dominate Search</h2>
          <p className="text-gray-400 mt-4 max-w-xl mx-auto">
            Six AI modules working together — technical SEO, keywords, content, GEO, competitors, and analytics.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-gray-900 border border-gray-800 rounded-2xl p-5 hover:border-gray-700 transition-colors group"
            >
              <div className="w-10 h-10 bg-gray-800 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                {f.icon}
              </div>
              <h3 className="text-white font-semibold mb-2 text-sm">{f.title}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Demo / proof section ──────────────────────────────────────────────────────
function DemoSection() {
  return (
    <section className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <p className="text-atlas-400 text-sm font-semibold uppercase tracking-wider mb-3">See it in action</p>
          <h2 className="text-4xl font-bold text-white">Stop Guessing. Know Exactly What to Fix.</h2>
          <p className="text-gray-400 mt-4 max-w-xl mx-auto">
            Atlas doesn't just find problems — it tells you exactly why they matter and how to fix them.
          </p>
        </div>

        {/* Mock action plan card */}
        <div className="bg-gray-900 border border-gray-800 rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-8 bg-atlas-500/20 rounded-lg flex items-center justify-center">
              <Zap size={16} className="text-atlas-400" />
            </div>
            <div>
              <p className="text-white font-semibold">Action Plan Ready</p>
              <p className="text-gray-500 text-xs">example-site.com · 42 actions generated</p>
            </div>
            <span className="ml-auto text-xs bg-atlas-500/20 text-atlas-300 px-2.5 py-1 rounded-full border border-atlas-500/30">
              18 pending
            </span>
          </div>

          <div className="space-y-3">
            {[
              {
                priority: 1,
                color: "bg-red-400",
                badge: "bg-red-500/20 text-red-400 border-red-500/30",
                label: "Urgent",
                title: "Fix missing meta descriptions on 14 pages",
                type: "Technical SEO",
                desc: "14 pages have no meta description. This directly reduces click-through rate from search results.",
              },
              {
                priority: 2,
                color: "bg-orange-400",
                badge: "bg-orange-500/20 text-orange-400 border-orange-500/30",
                label: "High",
                title: "Add FAQ schema to 3 service pages",
                type: "GEO Optimisation",
                desc: "Structured data makes your content eligible for rich results and improves AI citation rates.",
              },
              {
                priority: 2,
                color: "bg-orange-400",
                badge: "bg-orange-500/20 text-orange-400 border-orange-500/30",
                label: "High",
                title: "Publish 'best locksmith London' blog post",
                type: "Content",
                desc: "Competitor ranks #3 for this 2,400 vol/mo keyword. You have no targeting page.",
              },
              {
                priority: 3,
                color: "bg-yellow-400",
                badge: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
                label: "Medium",
                title: "Fix duplicate H1 tags on /services and /about",
                type: "Technical SEO",
                desc: "Multiple H1s confuse crawlers about the primary topic of the page.",
              },
            ].map((action, i) => (
              <div key={i} className="bg-gray-800/60 border border-gray-700/50 rounded-xl px-4 py-3.5 flex items-start gap-3">
                <div className="flex items-center gap-2 mt-0.5 shrink-0">
                  <span className={`w-2 h-2 rounded-full ${action.color}`} />
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${action.badge}`}>
                    {action.label}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium">{action.title}</p>
                  <p className="text-gray-500 text-xs mt-0.5">{action.desc}</p>
                </div>
                <span className="text-xs text-gray-600 shrink-0 mt-0.5">{action.type}</span>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-5">
            <Link
              href="/register"
              className="bg-atlas-500 hover:bg-atlas-600 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors flex items-center gap-1.5"
            >
              Get my action plan <ArrowRight size={14} />
            </Link>
            <span className="text-gray-600 text-xs">+38 more actions in the queue</span>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Free audit CTA ────────────────────────────────────────────────────────────
function FreeAuditSection() {
  return (
    <section id="audit" className="py-24 px-6 bg-gray-900/20">
      <div className="max-w-3xl mx-auto text-center">
        <p className="text-atlas-400 text-sm font-semibold uppercase tracking-wider mb-3">No login needed</p>
        <h2 className="text-4xl font-bold text-white mb-4">Try a Free Quick Audit</h2>
        <p className="text-gray-400 mb-8 max-w-lg mx-auto">
          Enter any URL and get a full page-by-page SEO report instantly — no account required.
          It's like Screaming Frog, built right into Atlas.
        </p>
        <Link
          href="/audit"
          className="inline-flex items-center gap-2 bg-white text-gray-900 font-bold px-8 py-4 rounded-xl text-base hover:bg-gray-100 transition-colors shadow-xl"
        >
          <Search size={18} />
          Run Free Audit Now
          <ChevronRight size={18} />
        </Link>
        <p className="text-gray-600 text-sm mt-4">No sign-up · No credit card · Results in seconds</p>
      </div>
    </section>
  );
}

// ── Final CTA ─────────────────────────────────────────────────────────────────
function FinalCTA() {
  return (
    <section className="py-24 px-6 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-atlas-500/10 rounded-full blur-3xl" />
      </div>
      <div className="relative max-w-3xl mx-auto text-center">
        <h2 className="text-5xl font-extrabold text-white mb-5 leading-tight">
          Ready to Automate Your SEO?
        </h2>
        <p className="text-gray-400 text-lg mb-10 max-w-xl mx-auto">
          Let Atlas handle the audits, keyword research, competitor analysis, and action planning —
          so you can focus on running your business.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/register"
            className="group bg-atlas-500 hover:bg-atlas-600 text-white font-bold px-10 py-4 rounded-xl text-lg transition-all shadow-2xl shadow-atlas-500/30 flex items-center gap-2"
          >
            Get Started Free
            <ArrowRight size={20} className="group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>
        <p className="text-gray-600 text-sm mt-6">
          Runs locally on your machine · Your data stays private
        </p>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="border-t border-gray-800 py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-atlas-500 rounded-md flex items-center justify-center">
            <Globe size={12} className="text-white" />
          </div>
          <span className="text-white font-bold text-sm">Atlas</span>
          <span className="text-gray-600 text-sm">SEO & GEO Agent</span>
        </div>
        <div className="flex items-center gap-6 text-sm text-gray-500">
          <Link href="/audit" className="hover:text-white transition-colors">Free Audit</Link>
          <Link href="/login" className="hover:text-white transition-colors">Sign In</Link>
          <Link href="/register" className="hover:text-white transition-colors">Register</Link>
        </div>
        <p className="text-gray-600 text-sm">© {new Date().getFullYear()} Atlas. All rights reserved.</p>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Navbar />
      <Hero />
      <Stats />
      <HowItWorks />
      <Features />
      <DemoSection />
      <FreeAuditSection />
      <FinalCTA />
      <Footer />
    </div>
  );
}
