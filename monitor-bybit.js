import { runScan } from "../../../lib/monitorCore.js";

export const config = { maxDuration: 10 };

export default async function handler(req, res) {
  const cronAuth = req.headers["authorization"] === `Bearer ${process.env.CRON_SECRET}`;
  const pingerAuth = process.env.MONITOR_SECRET && req.query.key === process.env.MONITOR_SECRET;
  if (!cronAuth && !pingerAuth) {
    return res.status(401).json({ error: "unauthorized" });
  }
  try {
    const result = await runScan(["bybit"]);
    return res.status(200).json({ ok: true, broker: "bybit", ...result });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message });
  }
}
