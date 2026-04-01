import dotenv from "dotenv";

dotenv.config({ path: "../.env" });

/** @type {import("next").NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
  }
};

export default nextConfig;
