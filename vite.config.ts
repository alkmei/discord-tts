import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  base: "/static/",
  plugins: [tailwindcss()],
  build: {
    outDir: path.resolve(__dirname, "static/dist"),
    manifest: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "./assets/main.ts"), // Path to your entry file
        styles: path.resolve(__dirname, "./assets/main.css"),
      },
    },
  },
  clearScreen: false,
});
