import { fileURLToPath } from "node:url";
import path from "node:path";
import createNextIntlPlugin from "next-intl/plugin";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const withNextIntl = createNextIntlPlugin("./src/lib/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Pins the pnpm-workspace root so the standalone build's node_modules
  // symlinks (which point into the hoisted `.pnpm` store) resolve at the
  // same relative depth wherever the standalone output is copied to.
  outputFileTracingRoot: path.join(__dirname, "../../"),
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

export default withNextIntl(nextConfig);
