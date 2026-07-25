const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export { API_URL }

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}
