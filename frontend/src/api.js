let sessionReady;
async function bootstrap() {
  const nonce = new URLSearchParams(location.hash.slice(1)).get('session');
  if (!nonce) return;
  history.replaceState(null, '', location.pathname + location.search);
  const response = await fetch('/api/session', {method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nonce})});
  if (!response.ok) throw new Error((await response.json()).error);
}
export async function api(path, data) {
  sessionReady ??= bootstrap();
  await sessionReady;
  const response = await fetch(`/api/${path}`, {credentials: 'same-origin',
    ...(data ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)} : {})});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '요청에 실패했습니다.');
  return body;
}
