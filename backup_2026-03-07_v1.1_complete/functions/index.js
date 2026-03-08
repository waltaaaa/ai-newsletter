/**
 * Cloud Functions for CAN-MACRO Dashboard.
 *
 * Two scheduled triggers:
 *   1. weeklyPipeline  — Monday 6 AM ET  (full 7-step pipeline)
 *   2. dailyIndicators — midnight ET      (hard-data refresh only)
 *
 * Both functions shell out to the Python pipeline via child_process.
 * The Python environment must be available on the Cloud Functions runtime
 * or these should be deployed as Cloud Run Jobs instead.
 *
 * For local testing:
 *   firebase emulators:start --only functions
 */

const { onSchedule } = require("firebase-functions/v2/scheduler");
const { logger } = require("firebase-functions");
const admin = require("firebase-admin");
const { execSync } = require("child_process");

admin.initializeApp();

// ── Weekly full pipeline: Monday 6:00 AM Eastern ─────────────────────
exports.weeklyPipeline = onSchedule(
  {
    schedule: "0 6 * * 1",        // cron: Monday 6 AM
    timeZone: "America/Toronto",
    timeoutSeconds: 1800,         // 30 min max
    memory: "1GiB",
  },
  async (event) => {
    logger.info("Starting weekly pipeline run...");
    const start = Date.now();

    try {
      // Record run start
      await admin.firestore()
        .collection("pipeline_runs")
        .add({
          type: "weekly",
          status: "running",
          startedAt: new Date().toISOString(),
        });

      // Execute the Python pipeline
      const result = execSync(
        "python update_dashboard.py 2>&1",
        {
          cwd: "/workspace",
          timeout: 1500000,  // 25 min
          env: { ...process.env },
        }
      );

      const elapsed = ((Date.now() - start) / 1000).toFixed(0);
      logger.info(`Weekly pipeline completed in ${elapsed}s`);

      await admin.firestore()
        .collection("pipeline_runs")
        .add({
          type: "weekly",
          status: "success",
          completedAt: new Date().toISOString(),
          elapsedSeconds: parseInt(elapsed),
        });
    } catch (err) {
      logger.error("Weekly pipeline failed:", err.message);

      await admin.firestore()
        .collection("pipeline_runs")
        .add({
          type: "weekly",
          status: "error",
          completedAt: new Date().toISOString(),
          error: err.message?.substring(0, 500),
        });
    }
  }
);

// ── Daily indicator refresh: midnight Eastern ────────────────────────
exports.dailyIndicators = onSchedule(
  {
    schedule: "0 0 * * *",        // cron: every day at midnight
    timeZone: "America/Toronto",
    timeoutSeconds: 600,          // 10 min max
    memory: "512MiB",
  },
  async (event) => {
    logger.info("Starting daily indicator refresh...");
    const start = Date.now();

    try {
      // Execute only the hard-data fetch step
      const result = execSync(
        "python update_dashboard.py --indicators-only 2>&1",
        {
          cwd: "/workspace",
          timeout: 540000,  // 9 min
          env: { ...process.env },
        }
      );

      const elapsed = ((Date.now() - start) / 1000).toFixed(0);
      logger.info(`Daily indicators completed in ${elapsed}s`);

      await admin.firestore()
        .collection("pipeline_runs")
        .add({
          type: "daily_indicators",
          status: "success",
          completedAt: new Date().toISOString(),
          elapsedSeconds: parseInt(elapsed),
        });
    } catch (err) {
      logger.error("Daily indicators failed:", err.message);

      await admin.firestore()
        .collection("pipeline_runs")
        .add({
          type: "daily_indicators",
          status: "error",
          completedAt: new Date().toISOString(),
          error: err.message?.substring(0, 500),
        });
    }
  }
);
