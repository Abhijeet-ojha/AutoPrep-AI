/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ["react-plotly.js"]
  }
};

export default nextConfig;
