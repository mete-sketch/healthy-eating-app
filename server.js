import http from 'http';
import https from 'https';

const PORT = 3001;
const ANTHROPIC_API_URL = 'api.anthropic.com';
const MODEL = 'claude-sonnet-4-20250514';

// Read API key from environment
const API_KEY = process.env.ANTHROPIC_API_KEY;
if (!API_KEY) {
  console.error('\n  Missing ANTHROPIC_API_KEY environment variable.');
  console.error('  Run the server like this:\n');
  console.error('    ANTHROPIC_API_KEY=sk-ant-... node server.js\n');
  process.exit(1);
}

const SYSTEM_PROMPT = `You are a friendly, supportive nutrition advisor embedded in a healthy eating app. The user will tell you a food they're thinking of eating. Analyse it and respond with ONLY valid JSON (no markdown, no code fences) in this exact format:

{
  "food": "<the food name, cleaned up>",
  "rating": <number 1-10>,
  "portion": "<recommended portion in everyday visual terms, e.g. 'about the size of your fist', 'a deck of cards worth'>",
  "calories": "<calorie estimate for that portion, e.g. '~350 calories'>",
  "explanation": "<2-3 sentences explaining the rating in a casual, supportive tone. Never shame. Be encouraging.>",
  "alternative": "<if rating < 6, suggest a healthier swap in 1 sentence. If rating >= 6, set to null>"
}

Guidelines:
- Be encouraging and positive, never judgmental
- Use everyday language, not clinical terms
- Portion sizes should use visual comparisons (fist, palm, deck of cards, tennis ball, etc.)
- Calorie estimates should be approximate and use the ~ symbol
- For healthy foods (7+), celebrate the choice
- For moderate foods (4-6), acknowledge it's okay and gently suggest improvements
- For less healthy foods (1-3), be kind — suggest it as an occasional treat and offer a swap
- The alternative field should be null (not a string "null") when rating >= 6`;

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try { resolve(JSON.parse(body)); }
      catch (e) { reject(new Error('Invalid JSON')); }
    });
    req.on('error', reject);
  });
}

function callAnthropic(food) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      model: MODEL,
      max_tokens: 500,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: `Analyse this food: ${food}` }]
    });

    const options = {
      hostname: ANTHROPIC_API_URL,
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(payload)
      }
    };

    const apiReq = https.request(options, (apiRes) => {
      let data = '';
      apiRes.on('data', chunk => data += chunk);
      apiRes.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (apiRes.statusCode !== 200) {
            reject(new Error(parsed.error?.message || `API error: ${apiRes.statusCode}`));
            return;
          }
          const text = parsed.content?.[0]?.text;
          if (!text) {
            reject(new Error('Empty response from API'));
            return;
          }
          // Parse the JSON response from Claude
          const result = JSON.parse(text);
          resolve(result);
        } catch (e) {
          reject(new Error('Failed to parse API response'));
        }
      });
    });

    apiReq.on('error', reject);
    apiReq.write(payload);
    apiReq.end();
  });
}

const server = http.createServer(async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === 'POST' && req.url === '/api/analyze') {
    try {
      const { food } = await parseBody(req);
      if (!food || typeof food !== 'string' || food.trim().length === 0) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Please provide a food to analyse.' }));
        return;
      }

      console.log(`Analysing: "${food.trim()}"`);
      const result = await callAnthropic(food.trim());
      console.log(`  -> Rating: ${result.rating}/10`);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } catch (err) {
      console.error('Error:', err.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // Serve the HTML file for any other GET request
  if (req.method === 'GET') {
    const fs = await import('fs');
    const path = await import('path');
    const filePath = path.join(import.meta.dirname, 'index.html');
    try {
      const html = fs.readFileSync(filePath, 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(html);
    } catch {
      res.writeHead(404);
      res.end('Not found');
    }
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, () => {
  console.log(`\n  Healthy Eating App server running!`);
  console.log(`  Open in your browser: http://localhost:${PORT}\n`);
});
