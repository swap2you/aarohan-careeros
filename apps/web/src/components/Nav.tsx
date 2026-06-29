"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

const links = [
  ["Overview", "/"],
  ["Fresh Jobs", "/jobs"],
  ["Job Connectors", "/connectors"],
  ["Shortlist", "/shortlist"],
  ["Approval Queue", "/approvals"],
  ["Applications", "/applications"],
  ["Company Ledger", "/companies"],
  ["Recruiter Signals", "/recruiter-signals"],
  ["Gmail Review", "/gmail-reviews"],
  ["Interviews", "/interviews"],
  ["Consulting (Preview)", "/consulting"],
  ["Reports", "/analytics"],
  ["Ask Aarohan", "/ask"],
  ["AI Usage", "/ai-usage"],
  ["Audit Log", "/audit"],
  ["Validation", "/validation"],
  ["Settings", "/settings"],
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <nav className="nav">
      <div className="brand">Aarohan CareerOS</div>
      <ul>
        {links.map(([label, href]) => (
          <li key={href}>
            <Link className={pathname === href ? "active" : ""} href={href}>
              {label}
            </Link>
          </li>
        ))}
      </ul>
      <div className="nav-user">
        <span>{user?.email}</span>
        <button type="button" onClick={() => logout()}>
          Logout
        </button>
      </div>
    </nav>
  );
}
