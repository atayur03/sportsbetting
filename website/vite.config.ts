import react from "@vitejs/plugin-react";
import { spawn } from "node:child_process";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  envDir: "..",
  plugins: [
    {
      name: "local-python-status-api",
      configureServer(server) {
        let cachedBody = "";
        let cachedAt = 0;
        const cacheTtlMs = 30_000;
        server.middlewares.use("/api/status", (_request, response) => {
          const now = Date.now();
          if (cachedBody && now - cachedAt < cacheTtlMs) {
            response.setHeader("Content-Type", "application/json");
            response.setHeader("Cache-Control", "no-store");
            response.statusCode = 200;
            response.end(cachedBody);
            return;
          }

          const repoRoot = path.resolve(__dirname, "..");
          const child = spawn("python", ["-m", "api.status"], {
            cwd: repoRoot,
            env: process.env,
          });
          let stdout = "";
          let stderr = "";
          child.stdout.on("data", (chunk: Buffer) => {
            stdout += chunk.toString();
          });
          child.stderr.on("data", (chunk: Buffer) => {
            stderr += chunk.toString();
          });
          child.on("close", (code) => {
            response.setHeader("Content-Type", "application/json");
            response.setHeader("Cache-Control", "no-store");
            if (code !== 0) {
              response.statusCode = 502;
              response.end(JSON.stringify({ error: stderr.trim() || `status API exited with code ${code}` }));
              return;
            }
            cachedBody = stdout;
            cachedAt = Date.now();
            response.statusCode = 200;
            response.end(stdout);
          });
        });
      },
    },
    react(),
  ],
});
