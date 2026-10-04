module.exports = async function handler(_req, res) {
  const url = "https://www.bcc.cd/marche-des-changes/cours-de-change";
  try {
    const response = await fetch(url, {
      headers: { "user-agent": "USD-CDF-BCC/2.0" },
      cache: "no-store"
    });
    if (!response.ok) throw new Error(`BCC HTTP ${response.status}`);
    const html = await response.text();
    const text = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
    const dateMatch = text.match(/Marché officiel des changes\s+(\d{2}\/\d{2}\/\d{4})/i);
    const rateMatch = text.match(/1\s*USD\s*=\s*([0-9\s.,]+)\s*CDF/i);
    if (!dateMatch || !rateMatch) throw new Error("Cours USD/CDF introuvable sur la page BCC");
    const raw = rateMatch[1].replace(/[\s\u202f]/g, "");
    const normalized = raw.includes(",") && raw.includes(".")
      ? (raw.lastIndexOf(",") > raw.lastIndexOf(".") ? raw.replace(/\./g, "").replace(",", ".") : raw.replace(/,/g, ""))
      : raw.replace(",", ".");
    const value = Number(normalized);
    if (!Number.isFinite(value)) throw new Error("Cours USD/CDF invalide");
    const [dd, mm, yyyy] = dateMatch[1].split("/");
    const isoDate = `${yyyy}-${mm}-${dd}`;
    res.setHeader("Cache-Control", "s-maxage=300, stale-while-revalidate=600");
    return res.status(200).json({ source: "Banque Centrale du Congo", date: isoDate, value, source_url: url });
  } catch (error) {
    return res.status(502).json({ error: "Impossible de lire le flux BCC", detail: String(error?.message || error) });
  }
};
