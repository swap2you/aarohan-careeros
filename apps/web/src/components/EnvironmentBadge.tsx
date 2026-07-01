"use client";

import { useEffect, useState } from "react";

import { authFetch } from "@/lib/api";

type EnvInfo = {
  badge: string;
  is_owner_stack: boolean;
  show_fixture_controls: boolean;
};

export function EnvironmentBadge() {
  const [env, setEnv] = useState<EnvInfo | null>(null);
  const fallbackBadge = process.env.NEXT_PUBLIC_DEPLOYMENT_BADGE || "OWNER LOCAL";

  useEffect(() => {
    authFetch("/api/environment")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setEnv(data))
      .catch(() => null);
  }, []);

  const badge = env?.badge || fallbackBadge;
  const className =
    badge === "OWNER LOCAL" ? "env-badge owner" : badge === "E2E TEST" ? "env-badge e2e" : "env-badge fixture";

  return (
    <span className={className} title={`Deployment: ${badge}`}>
      {badge}
    </span>
  );
}

export function useDeploymentEnvironment() {
  const [env, setEnv] = useState<EnvInfo | null>(null);

  useEffect(() => {
    authFetch("/api/environment")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setEnv(data))
      .catch(() => null);
  }, []);

  return {
    env,
    showFixtureControls: env?.show_fixture_controls ?? process.env.NEXT_PUBLIC_E2E_MODE === "true",
    isOwnerStack: env?.is_owner_stack ?? process.env.NEXT_PUBLIC_DEPLOYMENT_BADGE === "OWNER LOCAL",
  };
}
