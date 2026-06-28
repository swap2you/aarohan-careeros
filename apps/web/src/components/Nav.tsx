"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["Overview", "/"],
  ["Fresh Jobs", "/jobs"],
  ["Shortlist", "/shortlist"],
  ["Approval Queue", "/approvals"],
  ["Applications", "/applications"],
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
    </nav>
  );
}
