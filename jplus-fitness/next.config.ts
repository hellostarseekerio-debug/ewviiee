import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Mockup only: serve Unsplash placeholders directly, skipping the
    // Next.js optimizer so the static demo works without a running server.
    unoptimized: true,
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
};

export default nextConfig;
