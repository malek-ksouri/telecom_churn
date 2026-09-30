/**
 * Client HTTP typé : seul point d'appel à l'API (règle du projet).
 *
 * Les chemins et les réponses sont typés par `paths` (généré depuis l'OpenAPI). Les filtres
 * multi-valeurs sont envoyés en paramètres répétés (`?risk_level=High&risk_level=Medium`),
 * le format attendu par FastAPI.
 */
import type { paths } from "./schema";

export const API_BASE = "/api";

type GetPath = {
  [P in keyof paths]: paths[P] extends { get: object } ? P : never;
}[keyof paths];

type JsonResponse<Op> = Op extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : never;

export type GetResponse<P extends GetPath> = paths[P] extends { get: infer Op }
  ? JsonResponse<Op>
  : never;

export type QueryValue = string | number | boolean | readonly (string | number)[] | null | undefined;
export type QueryParams = Record<string, QueryValue>;

/** Erreur d'API lisible (message du champ `detail` de FastAPI quand il existe). */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function toSearchParams(params: QueryParams = {}): URLSearchParams {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const v of value as readonly (string | number)[]) search.append(key, String(v));
    } else {
      search.append(key, String(value));
    }
  }
  return search;
}

function fillPath(path: string, pathParams: Record<string, string | number>): string {
  return path.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = pathParams[name];
    if (value === undefined) throw new Error(`Paramètre de chemin manquant : ${name}`);
    return encodeURIComponent(String(value));
  });
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Erreur ${String(response.status)}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail)) message = "Paramètres invalides";
  } catch {
    // Corps non JSON : on garde le message générique.
  }
  if (response.status >= 500) message = "Le serveur n'a pas pu répondre. Réessayez.";
  return new ApiError(response.status, message);
}

/** GET typé : `apiGet("/api/kpis", { query: filtres })`. */
export async function apiGet<P extends GetPath>(
  path: P,
  options: {
    query?: QueryParams;
    pathParams?: Record<string, string | number>;
    signal?: AbortSignal;
  } = {},
): Promise<GetResponse<P>> {
  const url = fillPath(path, options.pathParams ?? {});
  const search = toSearchParams(options.query).toString();
  let response: Response;
  try {
    response = await fetch(search ? `${url}?${search}` : url, {
      headers: { Accept: "application/json" },
      signal: options.signal ?? null,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "API injoignable : vérifiez que le serveur est lancé (npm run dev:all).");
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as GetResponse<P>;
}

/** POST JSON (assistant) : réponse JSON typée par l'appelant. */
export async function apiPost<T>(url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? null : JSON.stringify(body),
    signal: signal ?? null,
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}
