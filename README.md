# Exnova Gateway API (FastAPI · Arquitectura Limpia)

API REST que expone, de forma segura y auditable, las operaciones de Exnova usando la librería
[`zagmi/exnova`](https://github.com/zagmi/exnova) (fork de `iqoptionapi`).

> ⚠️ **Aviso**: la librería es **no oficial** (ingeniería inversa del WebSocket). Puede romperse sin aviso y su uso
> puede ir contra los términos de la plataforma. Opera con riesgo de pérdida de capital. Empieza SIEMPRE en `PRACTICE`.

## Arquitectura

```
app/
├── domain/            # Núcleo puro: entidades, enums, excepciones y PUERTOS (BrokerGateway). Sin dependencias externas.
├── application/       # Casos de uso: AccountService, MarketService, TradingService + políticas + AUDITORÍA.
├── infrastructure/
│   └── exnova/gateway.py   # ADAPTADOR: único archivo que conoce la librería exnova.
├── interfaces/api/    # FastAPI: routers v1, schemas, auth por API key, middleware, manejo de errores.
├── core/              # Config por entorno, logging JSON, contexto (request_id / client_id), helper de auditoría.
├── bootstrap.py       # Composition root (inyección de dependencias).
└── main.py            # create_app() + lifespan
```

Regla de dependencias: `interfaces → application → domain ← infrastructure`. Cambiar de librería/broker = escribir otro
adaptador que cumpla `BrokerGateway`; el resto no se toca.

## Requisitos
* Python 3.11+ (probado en 3.12) · Git (para instalar la librería desde GitHub) · Docker (opcional)

## Levantar en local (paso a paso)
```bash
# 1. Entorno virtual + dependencias
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. Variables de entorno
cp .env.local.example .env.local      # edita EXNOVA_EMAIL y EXNOVA_PASSWORD (cuenta demo)
export APP_ENV=local                  # Windows PowerShell: $env:APP_ENV="local"

# 3. Ejecutar
uvicorn app.main:create_app --factory --reload --port 8000
```
* Swagger: http://localhost:8000/docs (deshabilitado en `prod`)
* Salud: `curl localhost:8000/health/live` · `curl localhost:8000/health/ready` (503 si no hay sesión con Exnova)

## Levantar con Docker
```bash
cp .env.dev.example .env.dev          # edita credenciales y API_KEYS
APP_ENV=dev docker compose up --build -d
docker compose logs -f api
```

## Entornos y variables
`APP_ENV` (local | dev | staging | prod) se define en la shell/Docker y selecciona `.env.<APP_ENV>`.
Precedencia: `.env` < `.env.<APP_ENV>` < variables del sistema. Referencia completa en `.env.example`.

| Variable | Descripción | Local | Dev | Staging | Prod |
|---|---|---|---|---|---|
| `APP_ENV` | Entorno | local | dev | staging | prod |
| `API_KEYS` | `nombre:clave,...` | opcional | requerida* | **obligatoria** | **obligatoria** |
| `EXNOVA_EMAIL` / `EXNOVA_PASSWORD` | Credenciales | archivo | archivo | secreto | **secreto** |
| `EXNOVA_ACCOUNT_TYPE` | PRACTICE / REAL | PRACTICE | PRACTICE | PRACTICE | PRACTICE→REAL tras aprobación |
| `TRADING_ENABLED` | Interruptor de órdenes | true | true | true | false por defecto |
| `ALLOW_REAL_TRADING` | Permite cuenta REAL | false | false | false | solo aquí puede ser true |
| `MAX_TRADE_AMOUNT` | Tope por orden | 5 | 10 | 10 | 5 |
| `LOG_LEVEL` / `LOG_FORMAT` | Logs | DEBUG/console | DEBUG/json | INFO/json | INFO/json |
| `DEBUG` | Modo debug | opcional | opcional | prohibido | prohibido |

\* recomendado; la validación obligatoria aplica en staging/prod.
La app **no arranca** si una combinación es insegura (p. ej. `REAL` fuera de prod, `DEBUG` en prod, sin `API_KEYS` en prod).

## Endpoints (prefijo `/api/v1`, cabecera `X-API-Key`)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health/live`, `/health/ready` | Liveness / readiness (sin auth) |
| GET/POST | `/session/status`, `/session/connect`, `/session/disconnect` | Sesión con Exnova |
| GET | `/account/balance` | Saldo de la cuenta activa |
| POST | `/account/switch` | `{"account_type":"PRACTICE"}` (REAL solo si la política lo permite) |
| GET | `/market/candles?asset=EURUSD&interval=60&count=100` | Velas |
| GET | `/market/assets/open?instrument=turbo` | Activos abiertos (llamada lenta) |
| GET | `/market/profits?asset=EURUSD` | Rentabilidad |
| POST | `/trading/orders` | Colocar orden |
| GET | `/trading/orders/{id}/result?timeout_seconds=70` | Resultado (espera hasta el cierre) |

```bash
H='X-API-Key: TU_CLAVE'
curl -X POST localhost:8000/api/v1/session/connect -H "$H"
curl localhost:8000/api/v1/account/balance -H "$H"
curl -X POST localhost:8000/api/v1/trading/orders -H "$H" -H 'Content-Type: application/json' \
     -d '{"asset":"EURUSD","direction":"call","amount":1,"expiration_minutes":1}'
```

## Logs y auditoría
| Archivo / salida | Contenido |
|---|---|
| stdout | Todo, en JSON (recolectar con Loki/ELK/CloudWatch) |
| `logs/app.log` | Log técnico (rotativo) |
| `logs/audit.log` | **Pista de auditoría** (rotativa, JSON, logger `audit`) |

Cada línea incluye `ts` (UTC), `request_id` (también en la cabecera `X-Request-ID`), `client_id` (nombre de la API key),
`action`, `outcome` y datos del evento. Eventos auditados: `session.connect/disconnect`, `account.switch`,
`trading.order.requested/rejected/placed/result`, `auth.api_key` (denegaciones). Contraseñas, tokens, SSID y API keys
se **redactan** automáticamente. Ejemplo:
```json
{"ts":"2026-10-07T15:02:11+00:00","level":"INFO","logger":"audit","env":"dev","message":"trading.order.placed",
 "action":"trading.order.placed","outcome":"success","order_id":"123456","asset":"EURUSD","direction":"call",
 "amount":1.0,"account_type":"PRACTICE","request_id":"9f1c...","client_id":"dev-team"}
```
Para auditoría formal: envía `audit.log` a almacenamiento inmutable/WORM o a tu SIEM y define retención según tu política.

## Pruebas
```bash
pytest        # usa un broker simulado (FakeGateway); no toca Exnova
```

## Escalabilidad y límites conocidos
* **Un worker por instancia**: la sesión WebSocket vive en memoria. Para escalar, despliega instancias independientes
  (una cuenta/sesión cada una) o separa la sesión en un servicio dedicado con cola (Redis/RabbitMQ).
* Las llamadas a la librería se serializan con un lock (no es thread-safe).
* Reconexión automática con backoff; no reintenta ante credenciales inválidas (evita bloqueos).
* Siguientes pasos naturales: persistir órdenes en PostgreSQL, rate limiting, métricas Prometheus, rotación de API keys.

## Si la librería cambia
Todo el acoplamiento está en `app/infrastructure/exnova/gateway.py` (`Exnova`, `connect`, `change_balance`, `buy`,
`get_candles`, `get_all_open_time`, `get_all_profit`, `get_async_order`). Verifica esos nombres contra la versión instalada.
