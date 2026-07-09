"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAsk } from "@/lib/askContext";

export default function AskPage() {
  const { openAsk } = useAsk();
  const router = useRouter();

  useEffect(() => {
    openAsk();
    router.replace("/");
  }, [openAsk, router]);

  return (
    <div className="page-header">
      <p className="muted">Opening Ask Aarohan assistant…</p>
    </div>
  );
}
