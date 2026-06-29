"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

const links = [
  ["Overview", "/"],
  ["Fresh Jobs", "/jobs"],
  ["Job Connectors", "/connectors"],
  ["Shortlist", "/shortlist"],
  ["Approval Queue", "/approvals"],
  ["Applications", "/applications"],
  ["Company Ledger", "/companies"],
  ["Recruiter Signals", "/recruiter-signals"],
  ["Interviews", "/interviews"],
  ["Consulting", "/consulting"],
  ["Reports", "/analytics"],
  ["AI Usage", "/ai-usage"],
  ["Audit Log", "/audit"],
  ["Validation", "/validation"],
  ["Settings", "/settings"],
];

export function Nav() {
  const pathname = usePathname();
  const { email, logout } = useAuth();

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
      <div className="nav-footer">
        <p className="nav-user">{email}</p>
        <button type="button" className="nav-logout" onClick={() => logout()}>
          Log out
        </button>
      </div>
    </nav>
  );
}
