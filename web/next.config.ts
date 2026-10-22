import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The repo's own AGENTS.md (at the root) is the agents' entry point.
  agentRules: false,
};

export default nextConfig;
