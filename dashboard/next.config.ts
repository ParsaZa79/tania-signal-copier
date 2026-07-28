import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit only the files required by the production server. The Docker runtime
  // stage copies this traced output instead of exporting the full dependency
  // tree used during compilation.
  output: "standalone",
  logging: {
    incomingRequests: {
      ignore: [/^\/api\/symbols\/[^/]+\/price(?:\?.*)?$/],
    },
  },
};

export default nextConfig;
