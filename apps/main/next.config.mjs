/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@fe-el-seka/ui", "@fe-el-seka/shared"],
};

export default nextConfig;
