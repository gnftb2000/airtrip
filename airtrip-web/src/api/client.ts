import type {
  Account,
  Airline,
  AirlineDetail,
  Airport,
  AirportDetail,
  ApiErrorBody,
  ImportResult,
  ImportStatus,
  LoginResponse,
  Page,
  PlanExport,
  Route,
  TravelPlan,
} from './types'

const BASE = '/api'
const TOKEN_KEY = 'airtrip.token'

export class ApiError extends Error {
  status: number
  body: ApiErrorBody | undefined

  constructor(status: number, message: string, body?: ApiErrorBody) {
    super(message)
    this.status = status
    this.body = body
  }
}

export function readToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function writeToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

type Query = Record<string, string | number | boolean | null | undefined>

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const suffix = search.toString()
  return suffix ? `${path}?${suffix}` : path
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = readToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the API. Is airtrip_api.py running?')
  }

  if (response.status === 204) return undefined as T

  const type = response.headers.get('Content-Type') ?? ''
  if (!response.ok) {
    let body: ApiErrorBody = {}
    if (type.includes('application/json')) {
      body = (await response.json().catch(() => ({}))) as ApiErrorBody
    }
    throw new ApiError(response.status, body.message ?? response.statusText, body)
  }

  if (type.includes('application/json')) return (await response.json()) as T
  return (await response.blob()) as unknown as T
}

const body = (value: unknown) => JSON.stringify(value)

export interface PlanPayload {
  name: string
  departure_date: string
  return_date: string
  route_ids?: number[]
}

export const api = {
  login(username: string, password: string) {
    return request<LoginResponse>(`${BASE}/auth/login`, {
      method: 'POST',
      body: body({ username, password }),
    })
  },

  me() {
    return request<Account>(`${BASE}/auth/me`)
  },

  // ---- airports
  airports(query?: Query) {
    return request<Page<Airport>>(withQuery(`${BASE}/airports`, query))
  },
  airport(iata: string) {
    return request<AirportDetail>(`${BASE}/airports/${iata}`)
  },
  airportRoutes(iata: string, query?: Query) {
    return request<Page<Route>>(withQuery(`${BASE}/airports/${iata}/routes`, query))
  },
  airportAirlines(iata: string, query?: Query) {
    return request<Page<Airline>>(withQuery(`${BASE}/airports/${iata}/airlines`, query))
  },
  airportDestinations(iata: string, query?: Query) {
    return request<Page<Airport>>(withQuery(`${BASE}/airports/${iata}/destinations`, query))
  },

  // ---- airlines
  airlines(query?: Query) {
    return request<Page<Airline>>(withQuery(`${BASE}/airlines`, query))
  },
  airline(iata: string) {
    return request<AirlineDetail>(`${BASE}/airlines/${iata}`)
  },
  airlineRoutes(iata: string, query?: Query) {
    return request<Page<Route>>(withQuery(`${BASE}/airlines/${iata}/routes`, query))
  },

  // ---- routes
  routes(query?: Query) {
    return request<Page<Route>>(withQuery(`${BASE}/routes`, query))
  },
  route(id: number) {
    return request<Route>(`${BASE}/routes/${id}`)
  },

  // ---- plans
  plans(query?: Query) {
    return request<Page<TravelPlan>>(withQuery(`${BASE}/plans`, query))
  },
  plan(id: number) {
    return request<TravelPlan>(`${BASE}/plans/${id}`)
  },
  createPlan(payload: PlanPayload) {
    return request<TravelPlan>(`${BASE}/plans`, { method: 'POST', body: body(payload) })
  },
  updatePlan(id: number, payload: Partial<PlanPayload>) {
    return request<TravelPlan>(`${BASE}/plans/${id}`, { method: 'PATCH', body: body(payload) })
  },
  deletePlan(id: number) {
    return request<void>(`${BASE}/plans/${id}`, { method: 'DELETE' })
  },
  planRoutes(id: number, query?: Query) {
    return request<Page<Route>>(withQuery(`${BASE}/plans/${id}/routes`, query))
  },
  addPlanRoutes(id: number, routeIds: number[]) {
    return request<TravelPlan>(`${BASE}/plans/${id}/routes`, {
      method: 'POST',
      body: body({ route_ids: routeIds }),
    })
  },
  removePlanRoute(id: number, routeId: number) {
    return request<TravelPlan>(`${BASE}/plans/${id}/routes/${routeId}`, { method: 'DELETE' })
  },
  async exportPlanJson(): Promise<PlanExport> {
    return request<PlanExport>(`${BASE}/plans/export?format=json`)
  },
  async exportPlanImage(): Promise<Blob> {
    return request<Blob>(`${BASE}/plans/export?format=image`, {
      headers: { Accept: 'image/png' },
    })
  },

  // ---- users (admin)
  users(query?: Query) {
    return request<Page<Account>>(withQuery(`${BASE}/users`, query))
  },
  user(username: string) {
    return request<Account>(`${BASE}/users/${encodeURIComponent(username)}`)
  },
  createUser(payload: { username: string; password: string; role?: 'user' }) {
    return request<Account>(`${BASE}/users`, { method: 'POST', body: body(payload) })
  },
  updateUser(username: string, payload: { is_active?: boolean; password?: string }) {
    return request<Account>(`${BASE}/users/${encodeURIComponent(username)}`, {
      method: 'PATCH',
      body: body(payload),
    })
  },
  deleteUser(username: string) {
    return request<void>(`${BASE}/users/${encodeURIComponent(username)}`, { method: 'DELETE' })
  },

  // ---- import (admin)
  importStatus() {
    return request<ImportStatus>(`${BASE}/import/status`)
  },
  uploadDatasets(files: { airports?: File; airlines?: File; routes?: File }) {
    const form = new FormData()
    if (files.airports) form.append('airports', files.airports)
    if (files.airlines) form.append('airlines', files.airlines)
    if (files.routes) form.append('routes', files.routes)
    return request<ImportResult>(`${BASE}/import`, { method: 'POST', body: form })
  },
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
