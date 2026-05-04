export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'content-type',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: CORS });

  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return new Response('Storage not configured', { status: 503, headers: CORS });

  let body;
  try { body = await req.json(); }
  catch { return new Response('Invalid JSON', { status: 400, headers: CORS }); }

  if (!body.id) return new Response('Missing id', { status: 400, headers: CORS });

  const res = await fetch(`${url}/rest/v1/transcripts?id=eq.${body.id}`, {
    method: 'PATCH',
    headers: {
      'apikey':        key,
      'Authorization': `Bearer ${key}`,
      'Content-Type':  'application/json',
      'Prefer':        'return=minimal',
    },
    body: JSON.stringify({ helpful: body.helpful }),
  });

  if (!res.ok) {
    const err = await res.text().catch(() => res.status);
    return new Response(`Upstream error: ${err}`, { status: 502, headers: CORS });
  }

  return new Response('ok', { status: 200, headers: CORS });
}
