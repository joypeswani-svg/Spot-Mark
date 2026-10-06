/**
 * webpack.config.js — TruthLens Extension
 *
 * Produces multiple entry points required by MV3:
 *   - service-worker.js          (background)
 *   - content/extractor.js       (content script)
 *   - content/highlighter.js     (content script)
 *   - content/video-overlay.js   (content script, all frames)
 *   - popup.js + popup.html      (React popup)
 *   - side-panel.js              (Chrome Side Panel)
 *   - options.js                 (Options page)
 *
 * All entry points are compiled to dist/ which is the unpacked extension folder.
 */

const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

const srcDir = path.resolve(__dirname, "src");
const distDir = path.resolve(__dirname, "dist");

module.exports = (env, argv) => {
  const isDev = argv.mode === "development";

  return {
    mode: isDev ? "development" : "production",
    devtool: isDev ? "inline-source-map" : false,

    // ── Entry points ──────────────────────────────────────────────────────
    entry: {
      // MV3 service worker — must be a single flat file
      "service-worker": path.join(srcDir, "background", "service-worker.ts"),

      // Content scripts
      "content/extractor": path.join(srcDir, "content", "extractor.ts"),
      "content/highlighter": path.join(srcDir, "content", "highlighter.ts"),
      "content/video-overlay": path.join(srcDir, "content", "video-overlay.ts"),

      // UI pages
      popup: path.join(srcDir, "popup", "index.tsx"),
      "side-panel": path.join(srcDir, "side-panel", "index.tsx"),
      options: path.join(srcDir, "options", "index.tsx"),
    },

    output: {
      path: distDir,
      filename: "[name].js",
      clean: true,
    },

    resolve: {
      extensions: [".ts", ".tsx", ".js", ".jsx"],
      alias: {
        "@truthlens/types": path.resolve(__dirname, "../../packages/types/src/index.ts"),
      },
    },

    module: {
      rules: [
        // TypeScript + React
        {
          test: /\.(ts|tsx)$/,
          use: {
            loader: "ts-loader",
            options: { configFile: path.resolve(__dirname, "tsconfig.json") },
          },
          exclude: /node_modules/,
        },
        // CSS (injected into shadow DOM or style tags)
        {
          test: /\.css$/,
          use: [MiniCssExtractPlugin.loader, "css-loader"],
        },
      ],
    },

    plugins: [
      // ── HTML pages ──────────────────────────────────────────────────────
      new HtmlWebpackPlugin({
        template: path.join(srcDir, "popup", "index.html"),
        filename: "popup.html",
        chunks: ["popup"],
      }),
      new HtmlWebpackPlugin({
        template: path.join(srcDir, "side-panel", "index.html"),
        filename: "side-panel.html",
        chunks: ["side-panel"],
      }),
      new HtmlWebpackPlugin({
        template: path.join(srcDir, "options", "index.html"),
        filename: "options.html",
        chunks: ["options"],
      }),

      // ── CSS extraction ───────────────────────────────────────────────────
      new MiniCssExtractPlugin({ filename: "[name].css" }),

      // ── Static assets ────────────────────────────────────────────────────
      new CopyWebpackPlugin({
        patterns: [
          // Manifest goes to dist root
          { from: path.resolve(__dirname, "manifest.json"), to: distDir },
          // Icons
          { from: path.resolve(__dirname, "public", "icons"), to: path.join(distDir, "icons") },
        ],
      }),
    ],

    // MV3 service workers cannot be code-split — prevent chunk splitting for SW
    optimization: {
      splitChunks: {
        chunks: (chunk) => chunk.name !== "service-worker",
      },
    },
  };
};
