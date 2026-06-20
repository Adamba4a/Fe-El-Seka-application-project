/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@fe-el-seka/ui", "@fe-el-seka/shared"],
  webpack(config, { nextRuntime, webpack }) {
    if (nextRuntime === "edge") {
      // @supabase/supabase-js reads process.version at module load and triggers
      // a Next.js 14 build warning in Edge Runtime (middleware). Stub it out.
      config.plugins.push(
        new webpack.DefinePlugin({ "process.version": JSON.stringify("18.0.0") })
      );
    }
    return config;
  },
};

export default nextConfig;
