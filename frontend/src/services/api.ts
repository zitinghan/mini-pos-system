import { translateError } from '../utils/i18n';
import { useAuth } from '../stores/auth';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(
  path: string, method = 'GET', body?: unknown, key?: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(useAuth.getState().token ? { Authorization: `Bearer ${useAuth.getState().token}` } : {}),
        ...(key ? { 'Idempotency-Key': key } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(20000),
    });
  } catch {
    throw new ApiError(0, '无法连接服务器。请检查店内 WiFi。订单状态未确认，请勿另建重复订单。');
  }
  if (!response.ok) {
    const result = await response.json().catch(() => ({ detail: 'Server error' }));
    if (response.status === 401) useAuth.getState().signOut();
    throw new ApiError(response.status, typeof result.detail === 'string'
      ? translateError(result.detail) : '输入有误，请检查后重试');
  }
  return response.json() as Promise<T>;
}

export function requestKey(scope: string): string {
  const storageKey = `koko-request:${scope}`;
  let key = localStorage.getItem(storageKey);
  if (!key) {
    // randomUUID requires HTTPS; HTTP LAN operation still needs a collision-resistant ID.
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    key = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    localStorage.setItem(storageKey, key);
  }
  return key;
}

export function clearKey(scope: string) {
  localStorage.removeItem(`koko-request:${scope}`);
}

export async function previewJob(id: number) {
  const response = await fetch(`/api/print-jobs/${id}/preview`, {
    headers: { Authorization: `Bearer ${useAuth.getState().token}` },
  });
  if (!response.ok) throw new Error('预览尚未生成');
  return URL.createObjectURL(await response.blob());
}
