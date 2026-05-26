export async function loadAppVersion() {
  try {
    const res = await fetch('http://127.0.0.1:8765/api/version', { cache: 'no-store' });
    if (!res.ok) throw new Error('version endpoint failed');
    const data = await res.json();
    return data.version || 'v1.4-full';
  } catch (e) {
    return 'v1.4-full';
  }
}
