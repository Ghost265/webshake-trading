export const API_BASE_URL = 'http://127.0.0.1:8765';

export async function apiGet(path, retries = 3) {
  let lastError;
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${API_BASE_URL}${path}`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (e) {
      lastError = e;
      await new Promise(r => setTimeout(r, 350));
    }
  }
  throw lastError;
}
