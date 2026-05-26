export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(200).end();

  const { url, method = "GET", headers = {}, body } = req.body;

  const finalHeaders = { ...headers };

  if (url.includes("anthropic.com")) {
    finalHeaders["x-api-key"] = process.env.ANTHROPIC_API_KEY;
    finalHeaders["anthropic-version"] = "2023-06-01";
  }

  if (url.includes("yahoo.com")) {
    finalHeaders["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
    finalHeaders["Accept"] = "application/json";
    finalHeaders["Accept-Language"] = "en-US,en;q=0.9";
    finalHeaders["Referer"] = "https://finance.yahoo.com";
  }

  try {
    const response = await fetch(url, {
      method,
      headers: finalHeaders,
      ...(body ? { body: typeof body === "string" ? body : JSON.stringify(body) } : {}),
    });
    const text = await response.text();
    try { res.status(200).json(JSON.parse(text)); }
    catch { res.status(200).json({ error: "Invalid JSON", raw: text.slice(0, 200) }); }
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
