import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Authenticated editor screens are dynamic; enable partial caching only after validation.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
