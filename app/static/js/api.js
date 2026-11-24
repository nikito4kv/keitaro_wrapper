// Запросы к нашему серверу. Любая ошибка превращается в ApiError с текстом для человека.

export class ApiError extends Error {
  constructor(message, { status = 0, fields = {} } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
  }
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('Приложение не отвечает. Проверьте, что сервер запущен, и обновите страницу.');
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // Пустой или не JSON ответ: ниже подставим общую фразу.
  }

  if (!response.ok) {
    const message = typeof data?.detail === 'string' ? data.detail : 'Не получилось выполнить запрос. Попробуйте ещё раз.';
    throw new ApiError(message, { status: response.status, fields: data?.fields ?? {} });
  }
  return data;
}
