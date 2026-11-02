// Shapes mirrored from the API's Swagger document (/swagger.json).

export interface Links {
  self?: string
  next?: string | null
  prev?: string | null
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  pages: number
  _links?: Links
}

export interface Account {
  id: number
  username: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
  _links?: Links
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  account: Account
}

export interface Airport {
  airport_id: number
  name: string
  city: string
  country: string
  iata_code: string
  icao_code: string | null
  latitude: number | null
  longitude: number | null
  altitude: number | null
  timezone: string | null
  _links?: Links
}

export interface AirportDetail extends Airport {
  route_count: number
  departure_route_count: number
  arrival_route_count: number
  airline_count: number
}

export interface Airline {
  airline_id: number
  name: string
  iata_code: string
  icao_code: string | null
  country: string
  _links?: Links
}

export interface AirlineDetail extends Airline {
  route_count: number
  airport_count: number
}

export interface Route {
  route_id: number
  airline_id: number
  airline_iata: string
  origin_airport_id: number
  origin_iata: string
  destination_airport_id: number
  destination_iata: string
  codeshare: string
  stops: number
  equipment: string | null
  _links?: Links
}

export interface RouteExpanded extends Route {
  airline: Airline
  origin_airport: Airport
  destination_airport: Airport
}

export interface TravelPlan {
  plan_id: number
  name: string
  departure_date: string
  return_date: string
  owner: string
  route_count: number
  created_at: string
  updated_at: string
  routes?: RouteExpanded[]
  _links?: Links
}

export interface ImportCounts {
  airports: number
  airlines: number
  routes: number
}

export interface ImportStatus {
  counts: ImportCounts
  last_import_at: string | null
  last_import: { imported?: ImportCounts; replaced?: string[]; message?: string } | null
}

export interface ImportResult {
  imported?: ImportCounts
  replaced?: string[]
  counts?: ImportCounts
  message: string
}

export interface PlanExport {
  account: string
  exported_at: string
  plan_count: number
  plans: TravelPlan[]
}

export interface ApiErrorBody {
  code?: number
  message?: string
}
