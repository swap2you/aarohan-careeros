"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

type NavItem = { label: string; href: string; icon: string };

type NavSection = { title: string; items: NavItem[] };

const sections: NavSection[] = [
  {
    title: "Command",
    items: [{ label: "Overview", href: "/", icon: "◈" }],
  },
  {
    title: "Pipeline",
    items: [
      { label: "Fresh Jobs", href: "/jobs", icon: "◎" },
      { label: "New Opportunity", href: "/opportunities/new", icon: "✦" },
      { label: "Job Connectors", href: "/connectors", icon: "⬡" },
      { label: "Shortlist", href: "/shortlist", icon: "◉" },
    ],
  },
  {
    title: "Workflow",
    items: [
      { label: "Approval Queue", href: "/approvals", icon: "▣" },
      { label: "Applications", href: "/applications", icon: "▤" },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { label: "Gmail Review", href: "/gmail-reviews", icon: "✉" },
      { label: "Interviews", href: "/interviews", icon: "◐" },
      { label: "Reports", href: "/analytics", icon: "▥" },
      { label: "AI Usage", href: "/ai-usage", icon: "◌" },
    ],
  },
  {
    title: "Records",
    items: [
      { label: "Company Ledger", href: "/companies", icon: "▦" },
      { label: "Recruiter Signals", href: "/recruiter-signals", icon: "◆" },
      { label: "Consulting", href: "/consulting", icon: "◇" },
      { label: "Audit Log", href: "/audit", icon: "▧" },
      { label: "Validation", href: "/validation", icon: "✓" },
      { label: "Settings", href: "/settings", icon: "⚙" },
    ],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <nav className="nav" aria-label="Main navigation">
      <div className="nav-brand">
        <div className="nav-logo" aria-hidden="true">
          <span className="nav-logo-core" />
          <span className="nav-logo-ring" />
        </div>
        <div>
          <div className="brand-title">CareerOS</div>
          <div className="brand-sub">Aarohan · Supervised ops</div>
        </div>
      </div>

      <div className="nav-scroll">
        {sections.map((section) => (
          <div key={section.title} className="nav-section">
            <div className="nav-section-label">{section.title}</div>
            <ul>
              {section.items.map(({ label, href, icon }) => (
                <li key={href}>
                  <Link
                    className={isActive(pathname, href) ? "active" : ""}
                    href={href}
                    aria-current={isActive(pathname, href) ? "page" : undefined}
                  >
                    <span className="nav-icon" aria-hidden="true">
                      {icon}
                    </span>
                    <span className="nav-label">{label}</span>
                    {isActive(pathname, href) && <span className="nav-active-glow" aria-hidden="true" />}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="nav-user">
        <div className="nav-user-avatar" aria-hidden="true">
          {(user?.email?.[0] ?? "U").toUpperCase()}
        </div>
        <div className="nav-user-meta">
          <span className="nav-user-email">{user?.email}</span>
          <span className="nav-user-role">Owner session</span>
        </div>
        <button type="button" className="nav-logout" onClick={() => logout()}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
