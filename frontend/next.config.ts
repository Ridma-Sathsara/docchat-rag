import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the root so a stray lockfile in a parent folder isn't mistaken for the workspace.
  turbopack: { root: __dirname },
};

export default nextConfig;
