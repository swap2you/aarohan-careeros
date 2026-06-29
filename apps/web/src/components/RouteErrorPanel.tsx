"use client";

import Link from "next/link";

type Props = {
  title: string;
  message: string;
  onRetry?: () => void;
  backHref?: string;
  backLabel?: string;
};

export function RouteErrorPanel({ title, message, onRetry, backHref = "/jobs", backLabel = "Back" }: Props) {
  return (
    <div className="card route-error">
      <h1>{title}</h1>
      <p>{message}</p>
      <div className="actions">
        {onRetry && (
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        )}
        <Link href={backHref}>{backLabel}</Link>
      </div>
    </div>
  );
}
