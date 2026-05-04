export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'content-type,anthropic-version,x-access-code',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS });
  }

  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405, headers: CORS });
  }

  const accessCode = process.env.ACCESS_CODE || '';
  if (accessCode && req.headers.get('x-access-code') !== accessCode) {
    return new Response('Invalid or missing access code', { status: 403, headers: CORS });
  }

  const upstream = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key':         process.env.ANTHROPIC_API_KEY,
      'anthropic-version': req.headers.get('anthropic-version') || '2023-06-01',
      'content-type':      'application/json',
    },
    body: req.body,
  });

  const responseHeaders = new Headers(CORS);
  for (const [k, v] of upstream.headers) {
    if (!['transfer-encoding', 'connection', 'content-length'].includes(k)) {
      responseHeaders.set(k, v);
    }
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
