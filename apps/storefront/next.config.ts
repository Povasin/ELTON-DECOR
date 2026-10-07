import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@elton/api-client", "@elton/ui"],
  poweredByHeader: false,
};

export default nextConfig;
