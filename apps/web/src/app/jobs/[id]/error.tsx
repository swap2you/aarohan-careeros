"use client";

import { useEffect } from "react";

import { RouteErrorPanel } from "@/components/RouteErrorPanel";

export default function JobDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Job detail error:", error.message);
  }, [error]);

  return (
    <RouteErrorPanel
      title="Something went wrong"
      message="This job page encountered an unexpected error. Your session is still active."
      onRetry={reset}
      backHref="/jobs"
      backLabel="Back to Jobs"
    />
  );
}
