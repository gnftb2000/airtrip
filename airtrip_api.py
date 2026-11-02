"""AirTrip - airline operations REST API.

A Flask + SQLAlchemy service with JWT authentication and Swagger (OpenAPI)
documentation, backed by a local SQLite database.
"""
from __future__ import annotations

import io
import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlencode

import pandas as pd
from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    request,
    send_file,
    send_from_directory,
)
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from flask_jwt_extended.exceptions import JWTExtendedException
from flask_restx import Api, Namespace, Resource, fields, reqparse
from flask_sqlalchemy import SQLAlchemy
from jwt.exceptions import PyJWTError
from rapidfuzz import fuzz as rapidfuzz_fuzz, process as rapidfuzz_process
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
# ---------------------------------------------------------------------------
# Authentication and account administration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Swagger models and validation constants
# ---------------------------------------------------------------------------

username_pattern = re.compile(r"^[A-Za-z0-9_.-]+$")
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32
PASSWORD_MIN_LENGTH = 4
PASSWORD_MAX_LENGTH = 128

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "airtrip.db")

ACCESS_TOKEN_TTL = timedelta(hours=2)
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ALLOWED_ROLES = (ROLE_ADMIN, ROLE_USER)

JWT_SECURITY = "Bearer"

API_DESCRIPTION = """
## AirTrip - Airline Operations API

A RESTful service for exploring airline operations data and for building
private travel plans. All data is persisted in a local **SQLite** database
(`airtrip.db`) that is created next to the application file on first run.

### Authentication
The API uses **JWT bearer tokens** (`Authorization: Bearer <token>`).

1. `POST /api/auth/login` with `{"username": "...", "password": "..."}`.
2. Copy the returned `access_token` and click **Authorize** above.
3. Every protected endpoint re-checks the token on every request and also verifies
   that the account still exists and is **active**, so deactivating an account
   takes effect immediately.

Two accounts are seeded on first run: `admin` / `admin` (role `admin`) and
`user` / `user` (role `user`).

### Roles
| Capability | `admin` | `user` |
|     ---     |    ---   |   ---    |
| Browse airports, airlines, routes | yes | yes |
| Own travel plans (CRUD, export) | yes | yes |
| Create / list / delete accounts | yes | no |
| Activate / deactivate accounts | yes | no |
| Import CSV datasets | yes | no |

Resources owned by an account (travel plans) are **private**: even the `admin`
can only see and manage travel plans that the `admin` account itself created.
Accessing somebody else's plan returns `404`, so the API never leaks whether a
foreign plan exists.

### Error format
Every error uses the same envelope:

```json
{"code": 404, "message": "Airport 'XYZ' was not found."}
Validation errors may add a details list:

{"code": 400, "message": "Request validation failed.",
 "details": [{"field": "return_date", "issue": "must not be earlier than departure_date"}]}

Pagination
Every collection endpoint supports page (1-based, default 1) and page_size (default 20, maximum 100) and returns:

{"items": [...], "page": 1, "page_size": 20, "total": 260, "pages": 13,
 "_links": {"self": "...", "next": "...", "prev": null}}

"""

def utcnow() -> datetime:
    """Current UTC time as a *naive* datetime (SQLite stores no timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


db = SQLAlchemy()

class Account(db.Model):
    """An API account. Only one account has the ``admin`` role."""

    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(8), nullable=False, default=ROLE_USER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    plans = db.relationship(
        "TravelPlan",
        backref="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        try:
            return check_password_hash(self.password_hash, raw_password)
        except (ValueError, TypeError):
            return False

class Airline(db.Model):
    """An airline copied from ``airlines.csv``."""

    __tablename__ = "airlines"

    airline_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.String(120), nullable=False)
    iata_code = db.Column(db.String(2), unique=True, nullable=False, index=True)
    icao_code = db.Column(db.String(3), unique=True, nullable=False)
    country = db.Column(db.String(64), nullable=False)

class Airport(db.Model):
    """An airport copied from ``airports.csv``.
    CSV 里 id 是稳定业务主键，重复导入同一个文件结果幂等；
    routes.csv 用它做外键，如果数据库自己重排 id，你就得额外维护 id 映射表；
    替换式导入时可以直接 DELETE + INSERT 原值，不需要先清空再重新分配。
    """

    __tablename__ = "airports"

    airport_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(80), nullable=False)
    iata_code = db.Column(db.String(3), unique=True, nullable=False, index=True)
    icao_code = db.Column(db.String(4), unique=True, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    altitude = db.Column(db.Integer, nullable=False)
    timezone = db.Column(db.String(64), nullable=False)

class Route(db.Model):
    """A directed route from an origin airport to a destination airport.

    两次引用 airports（origin 和 destination），所以两个关系都要显式指定外键。
    """

    __tablename__ = "routes"

    route_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    airline_id = db.Column(
        db.Integer, db.ForeignKey("airlines.airline_id"), nullable=False, index=True
    )
    airline_iata = db.Column(db.String(2), nullable=False)
    origin_airport_id = db.Column(
        db.Integer, db.ForeignKey("airports.airport_id"), nullable=False, index=True
    )
    origin_iata = db.Column(db.String(3), nullable=False)
    destination_airport_id = db.Column(
        db.Integer, db.ForeignKey("airports.airport_id"), nullable=False, index=True
    )
    destination_iata = db.Column(db.String(3), nullable=False)
    codeshare = db.Column(db.String(1), nullable=True)
    stops = db.Column(db.Integer, nullable=False, default=0)
    equipment = db.Column(db.String(20), nullable=True)

    airline = db.relationship("Airline", backref="routes", lazy="joined")
    origin = db.relationship(
        "Airport", foreign_keys=[origin_airport_id], backref="departing_routes",
        lazy="joined",
    )
    destination = db.relationship(
        "Airport", foreign_keys=[destination_airport_id], backref="arriving_routes",
        lazy="joined",
    )


# Association table linking travel plans to the routes they contain.
plan_routes = db.Table(
    "plan_routes",
    db.Column(
        "plan_id",
        db.Integer,
        db.ForeignKey("travel_plans.plan_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "route_id", db.Integer, db.ForeignKey("routes.route_id"), primary_key=True
    ),
    db.Column("added_at", db.DateTime, nullable=False, default=utcnow),
)

class TravelPlan(db.Model):
    """A private, named collection of routes owned by exactly one account."""

    __tablename__ = "travel_plans"
    __table_args__ = (
        db.UniqueConstraint("owner_id", "name", name="uq_plan_owner_name"),
    )

    plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), nullable=False)
    departure_date = db.Column(db.Date, nullable=False, index=True)
    return_date = db.Column(db.Date, nullable=False)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    routes = db.relationship(
        "Route", secondary=plan_routes, backref="plans", lazy="selectin"
    )


# Flask application configuration: SQLite database, JWT settings and Flask-RESTX.
app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JWT_SECRET_KEY=os.environ.get(
        "AIRTRIP_JWT_SECRET", "airtrip-dev-secret-change-me"
    ),
    JWT_ACCESS_TOKEN_EXPIRES=ACCESS_TOKEN_TTL,
    JWT_TOKEN_LOCATION=["headers"],
    JWT_HEADER_TYPE="Bearer",
    RESTX_VALIDATE=False,
    # Without this Flask-RESTX appends "but did you mean ... ?" to every 404
    # message, which would break the fixed error envelope documented in Swagger.
    RESTX_ERROR_404_HELP=False,
)

db.init_app(app)
jwt = JWTManager(app)

# 配置 Swagger 的「Authorize」按钮
authorizations = {
    JWT_SECURITY: {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Paste **Bearer &lt;access_token&gt;** here "
        "(the word `Bearer`, one space, then the token).",
    }
}


# Api 本体
api = Api(
    app,
    version="1.0.0",
    title="AirTrip - Airline Operations API",
    description=API_DESCRIPTION,
    # Swagger UI lives at /docs so the site root can serve the web client.
    doc="/docs",
    authorizations=authorizations,
    validate=False,
)


# Namespace objects are created here so that every module below can attach
# resources to the correct group. Paths carry the /api prefix explicitly so the
# Swagger UI can live at "/".
# 创建 7 个 Namespace 并注册：
auth_ns = Namespace("auth", description="Authentication and token management",
                    path="/api/auth")
users_ns = Namespace("users", description="Account administration (admin only)",
                     path="/api/users")
import_ns = Namespace("import", description="Import CSV datasets (admin only)",
                      path="/api/import")
airports_ns = Namespace("airports", description="Explore airports",
                        path="/api/airports")
airlines_ns = Namespace("airlines", description="Explore airlines",
                        path="/api/airlines")
routes_ns = Namespace("routes", description="Explore routes", path="/api/routes")
plans_ns = Namespace("plans", description="Private travel plans and export",
                     path="/api/plans")

for _ns in (auth_ns, users_ns, import_ns, airports_ns, airlines_ns, routes_ns,
            plans_ns):
    api.add_namespace(_ns)

# 共享 helper：错误、分页、鉴权

# 统一错误：abort_json
def abort_json(status: int, message: str, details=None):
    """Abort the request with the API-wide error envelope."""
    payload = {"code": status, "message": message}
    if details:
        payload["details"] = details
    error = HTTPException(description=message)
    error.code = status
    error.data = payload  # flask-restx uses ``e.data`` verbatim as the body
    raise error

# 日期、时间与请求体
def iso_utc(value):
    """Render a naive UTC datetime as an ISO-8601 string ending in ``Z``."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(value, field_name):
    """Parse a ``YYYY-MM-DD`` string, aborting with 400 on bad input."""
    if not isinstance(value, str):
        abort_json(400, f"'{field_name}' must be a string in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        abort_json(400, f"'{field_name}' must be a valid date in YYYY-MM-DD format.")


def json_body(*required_fields):
    """Return the request JSON object and ensure required keys are present."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort_json(400, "Request body must be a JSON object.")
    missing = [name for name in required_fields if name not in payload]
    if missing:
        abort_json(400, f"Missing required field(s): {', '.join(missing)}.")
    return payload

def page_arguments():
    """Validate and return ``(page, page_size)`` from the query string."""
    raw_page = request.args.get("page", "1")
    raw_size = request.args.get("page_size", str(DEFAULT_PAGE_SIZE))
    try:
        page = int(raw_page)
        page_size = int(raw_size)
    except (TypeError, ValueError):
        abort_json(400, "'page' and 'page_size' must be integers.")
    if page < 1:
        abort_json(400, "'page' must be greater than or equal to 1.")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        abort_json(
            400, f"'page_size' must be between 1 and {MAX_PAGE_SIZE}."
        )
    return page, page_size


def page_links(page: int, pages: int) -> dict:
    """Build ``self``/``next``/``prev`` links for a paginated collection."""
    base = request.base_url
    args = request.args.to_dict(flat=True)

    def link(target):
        query = dict(args)
        query["page"] = target
        return f"{base}?{urlencode(query)}"

    return {
        "self": link(page),
        "next": link(page + 1) if page < pages else None,
        "prev": link(page - 1) if page > 1 else None,
    }

# 分页
def paginated(items, page: int, page_size: int, total: int) -> dict:
    """Wrap a slice of rows in the standard pagination envelope."""
    pages = math.ceil(total / page_size) if total else 0
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
        "_links": page_links(page, pages),
    }


# 当前账号、admin 装饰器、所有权检查
def current_account() -> Account:
    """Resolve the account behind the JWT and enforce the active flag.

    The account is looked up in the database on *every* request. That is what
    makes ``is_active`` revocation immediate instead of waiting for the token
    to expire.
    每次查库 + 检查 is_active
    """
    username = get_jwt_identity()
    account = Account.query.filter_by(username=username).first()
    if account is None:
        abort_json(401, "The account linked to this token no longer exists.")
    if not account.is_active:
        abort_json(403, "This account has been deactivated.")
    return account


def admin_required(view):
    """Require a valid token belonging to an active ``admin`` account."""

    @wraps(view)
    @jwt_required()
    def wrapper(*args, **kwargs):
        account = current_account()
        if account.role != ROLE_ADMIN:
            abort_json(403, "Admin privileges are required for this operation.")
        return view(*args, **kwargs)

    return wrapper


def get_owned_plan(plan_id: int) -> TravelPlan:
    """Return the caller's plan, or 404 when missing or owned by someone else."""
    account = current_account()
    plan = db.session.get(TravelPlan, plan_id)
    if plan is None or plan.owner_id != account.id:
        abort_json(404, f"Travel plan {plan_id} was not found for this account.")
    return plan


# 去重小工具
def unique(items):
    """De-duplicate a list of model instances while preserving order."""
    seen, out = set(), []
    for item in items:
        key = item.airline_id if isinstance(item, Airline) else item.airport_id
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

# 序列化器：ORM 对象 → JSON
def serialize_account(account: Account) -> dict:
    """Public representation of an account. Never exposes the password hash."""
    return {
        "id": account.id,
        "username": account.username,
        "role": account.role,
        "is_active": account.is_active,
        "created_at": iso_utc(account.created_at),
        "_links": {"self": f"/api/users/{account.username}"},
    }


def serialize_airline(airline: Airline) -> dict:
    return {
        "airline_id": airline.airline_id,
        "name": airline.name,
        "iata_code": airline.iata_code,
        "icao_code": airline.icao_code,
        "country": airline.country,
        "_links": {
            "self": f"/api/airlines/{airline.iata_code}",
            "routes": f"/api/airlines/{airline.iata_code}/routes",
        },
    }


def serialize_airport(airport: Airport) -> dict:
    return {
        "airport_id": airport.airport_id,
        "name": airport.name,
        "city": airport.city,
        "country": airport.country,
        "iata_code": airport.iata_code,
        "icao_code": airport.icao_code,
        "latitude": airport.latitude,
        "longitude": airport.longitude,
        "altitude": airport.altitude,
        "timezone": airport.timezone,
        "_links": {
            "self": f"/api/airports/{airport.iata_code}",
            "routes": f"/api/airports/{airport.iata_code}/routes",
            "airlines": f"/api/airports/{airport.iata_code}/airlines",
        },
    }


def serialize_route(route: Route, expand: bool = False) -> dict:
    data = {
        "route_id": route.route_id,
        "airline_id": route.airline_id,
        "airline_iata": route.airline_iata,
        "origin_airport_id": route.origin_airport_id,
        "origin_iata": route.origin_iata,
        "destination_airport_id": route.destination_airport_id,
        "destination_iata": route.destination_iata,
        "codeshare": route.codeshare,
        "stops": route.stops,
        "equipment": route.equipment,
        "_links": {
            "self": f"/api/routes/{route.route_id}",
            "airline": f"/api/airlines/{route.airline_iata}",
            "origin": f"/api/airports/{route.origin_iata}",
            "destination": f"/api/airports/{route.destination_iata}",
        },
    }
    if expand:
        data["airline"] = serialize_airline(route.airline)
        data["origin_airport"] = serialize_airport(route.origin)
        data["destination_airport"] = serialize_airport(route.destination)
    return data


def serialize_plan(plan: TravelPlan, expand_routes: bool = False) -> dict:
    data = {
        "plan_id": plan.plan_id,
        "name": plan.name,
        "departure_date": plan.departure_date.isoformat(),
        "return_date": plan.return_date.isoformat(),
        "owner": plan.owner.username if plan.owner else None,
        "route_count": len(plan.routes),
        "created_at": iso_utc(plan.created_at),
        "updated_at": iso_utc(plan.updated_at),
        "_links": {
            "self": f"/api/plans/{plan.plan_id}",
            "routes": f"/api/plans/{plan.plan_id}/routes",
        },
    }
    if expand_routes:
        data["routes"] = [serialize_route(r, expand=True) for r in plan.routes]
    return data


# Swagger 文档模型
error_model = api.model(
    "Error",
    {
        "code": fields.Integer(description="HTTP status code", example=404),
        "message": fields.String(description="Human readable error message"),
    },
)

links_model = api.model("Links", {"self": fields.String, "next": fields.String,
                                 "prev": fields.String})

account_model = api.model(
    "Account",
    {
        "id": fields.Integer(example=2),
        "username": fields.String(example="user"),
        "role": fields.String(example="user", enum=["admin", "user"]),
        "is_active": fields.Boolean(example=True),
        "created_at": fields.String(example="2026-10-26T02:30:00Z"),
        "_links": fields.Raw,
    },
)

login_model = api.model(
    "LoginRequest",
    {
        "username": fields.String(required=True, example="admin"),
        "password": fields.String(required=True, example="admin"),
    },
)

token_model = api.model(
    "TokenResponse",
    {
        "access_token": fields.String,
        "token_type": fields.String(example="Bearer"),
        "expires_in": fields.Integer(example=7200),
        "account": fields.Nested(account_model),
    },
)

airline_model = api.model(
    "Airline",
    {
        "airline_id": fields.Integer(example=1),
        "name": fields.String(example="Qantas"),
        "iata_code": fields.String(example="QF"),
        "icao_code": fields.String(example="QFA"),
        "country": fields.String(example="Australia"),
        "_links": fields.Raw,
    },
)

airport_model = api.model(
    "Airport",
    {
        "airport_id": fields.Integer(example=1),
        "name": fields.String(example="Sydney Kingsford Smith Airport"),
        "city": fields.String(example="Sydney"),
        "country": fields.String(example="Australia"),
        "iata_code": fields.String(example="SYD"),
        "icao_code": fields.String(example="YSSY"),
        "latitude": fields.Float(example=-33.9461),
        "longitude": fields.Float(example=151.1772),
        "altitude": fields.Integer(example=6),
        "timezone": fields.String(example="Australia/Sydney"),
        "_links": fields.Raw,
    },
)

route_model = api.model(
    "Route",
    {
        "route_id": fields.Integer(example=1),
        "airline_id": fields.Integer(example=1),
        "airline_iata": fields.String(example="QF"),
        "origin_airport_id": fields.Integer(example=1),
        "origin_iata": fields.String(example="SYD"),
        "destination_airport_id": fields.Integer(example=2),
        "destination_iata": fields.String(example="MEL"),
        "codeshare": fields.String(example=None, allow_null=True),
        "stops": fields.Integer(example=0),
        "equipment": fields.String(example="789"),
        "_links": fields.Raw,
    },
)

route_expanded_model = api.model(
    "RouteExpanded",
    {
        "route_id": fields.Integer,
        "airline_iata": fields.String,
        "origin_iata": fields.String,
        "destination_iata": fields.String,
        "stops": fields.Integer,
        "equipment": fields.String,
        "airline": fields.Nested(airline_model),
        "origin_airport": fields.Nested(airport_model),
        "destination_airport": fields.Nested(airport_model),
        "_links": fields.Raw,
    },
)

plan_model = api.model(
    "TravelPlan",
    {
        "plan_id": fields.Integer(example=1),
        "name": fields.String(example="Japan Spring Trip"),
        "departure_date": fields.String(example="2027-04-01"),
        "return_date": fields.String(example="2027-04-15"),
        "owner": fields.String(example="user"),
        "route_count": fields.Integer(example=2),
        "created_at": fields.String,
        "updated_at": fields.String,
        "routes": fields.List(fields.Nested(route_expanded_model)),
        "_links": fields.Raw,
    },
)

# collection_model() 是个工厂：传入 ("AirportPage", airport_model)
# 就生成一个带分页信封的机场列表模型。
def collection_model(name: str, item_model) -> fields.Raw:
    """Build a pagination envelope model around ``item_model``."""
    return api.model(
        name,
        {
            "items": fields.List(fields.Nested(item_model)),
            "page": fields.Integer(example=1),
            "page_size": fields.Integer(example=20),
            "total": fields.Integer(example=260),
            "pages": fields.Integer(example=13),
            "_links": fields.Nested(links_model),
        },
    )

# 全局错误处理模块
@api.errorhandler(HTTPException)
def handle_http_exception(error):
    """Return the API-wide envelope for every HTTP error."""
    status = error.code if error.code is not None else 500
    return {"code": status, "message": error.description or "Request failed."}, status


def _handle_jwt_error(error):
    """Map flask-jwt-extended / PyJWT failures onto a 401 envelope.

    Flask-RESTX replaces Flask's exception routing for API views, so the
    error handlers flask-jwt-extended installs on the Flask app are never
    reached. Registering them on the Api restores the 401 behaviour.
    """
    return {"code": 401, "message": f"Authentication failed: {error}"}, 401


api.errorhandler(JWTExtendedException)(_handle_jwt_error)
api.errorhandler(PyJWTError)(_handle_jwt_error)


@api.errorhandler(Exception)
def handle_unexpected_error(error):  # pragma: no cover - defensive
    app.logger.exception("Unhandled error: %s", error)
    return {"code": 500, "message": "An unexpected internal error occurred."}, 500


# Requests that never reach a Flask-RESTX view (unknown path, wrong method)
# are handled by Flask itself; keep the error envelope consistent here too.
@app.errorhandler(HTTPException)
def handle_flask_http_exception(error):
    """Cover requests that never reach a Flask-RESTX view (unknown path, bad method)."""
    message = error.description
    if error.code == 404:
        message = "The requested URL was not found on this server."
    return jsonify({"code": error.code, "message": message}), error.code


@jwt.unauthorized_loader
def missing_token(reason):
    return jsonify({"code": 401, "message": f"Authorization required. {reason}"}), 401


@jwt.invalid_token_loader
def invalid_token(reason):
    return jsonify({"code": 401, "message": f"Invalid token. {reason}"}), 401


@jwt.expired_token_loader
def expired_token(_header, _payload):
    return jsonify({"code": 401, "message": "The access token has expired."}), 401


@jwt.revoked_token_loader
def revoked_token(_header, _payload):
    return jsonify({"code": 401, "message": "The access token has been revoked."}), 401


# 首次运行自动建库 + 种两个账号
DEFAULT_ACCOUNTS = (
    ("admin", "admin", ROLE_ADMIN),
    ("user", "user", ROLE_USER),
)


def seed_default_accounts() -> None:
    """Create the default accounts once, without touching later changes."""
    created = False
    for username, password, role in DEFAULT_ACCOUNTS:
        if Account.query.filter_by(username=username).first() is None:
            account = Account(username=username, role=role, is_active=True)
            account.set_password(password)
            db.session.add(account)
            created = True
    if created:
        db.session.commit()

# Never call db.drop_all() here: data must survive restarts.
with app.app_context():
    db.create_all()
    seed_default_accounts()

# 三个 Swagger 模型 + 列表查询 parser
user_create_model = api.model(
    "UserCreate",
    {
        "username": fields.String(
            required=True,
            description=(
                "Unique username, 3-32 characters. Allowed characters are "
                "letters, digits, dot, underscore and hyphen."
            ),
            example="alice",
        ),
        "password": fields.String(
            required=True,
            description="Plain-text password, 4-128 characters.",
            example="s3cret-pass",
        ),
        "role": fields.String(
            description=(
                "Role of the new account. Only `user` may be created: there is "
                "exactly one administrator account, so sending `admin` is "
                "rejected with 403."
            ),
            enum=["user"],
            default="user",
            example="user",
        ),
    },
)

user_update_model = api.model(
    "UserUpdate",
    {
        "is_active": fields.Boolean(
            description=(
                "Activate (`true`) or deactivate (`false`) the account. A "
                "deactivated account keeps its data but can no longer log in "
                "or use the API. The administrator account cannot be "
                "deactivated (409)."
            ),
            example=False,
        ),
        "password": fields.String(
            description="Replacement plain-text password, 4-128 characters.",
            example="new-s3cret",
        ),
    },
)

users_list_parser = reqparse.RequestParser()
users_list_parser.add_argument(
    "is_active",
    type=str,
    location="args",
    required=False,
    help="Filter by activation state: 'true' or 'false'.",
)
users_list_parser.add_argument(
    "role",
    type=str,
    location="args",
    required=False,
    help="Filter by role: 'admin' or 'user'.",
)
users_list_parser.add_argument(
    "q",
    type=str,
    location="args",
    required=False,
    help="Case-insensitive substring match on the username.",
)

users_page_model = collection_model("AccountPage", account_model)


# ---------------------------------------------------------------------------
# Helpers shared by the account resources
# ---------------------------------------------------------------------------


def validate_username(value):
    """Validate a username field and return its normalised value."""
    if not isinstance(value, str):
        abort_json(400, "'username' must be a string.")
    username = value.strip()
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        abort_json(
            400,
            f"'username' must be between {USERNAME_MIN_LENGTH} and "
            f"{USERNAME_MAX_LENGTH} characters long.",
        )
    if username_pattern.fullmatch(username) is None:
        abort_json(
            400,
            "'username' may only contain letters, digits, dots, underscores "
            "and hyphens.",
        )
    return username


def validate_password(value):
    """Validate a password field and return it unchanged."""
    if not isinstance(value, str):
        abort_json(400, "'password' must be a string.")
    if not PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH:
        abort_json(
            400,
            f"'password' must be between {PASSWORD_MIN_LENGTH} and "
            f"{PASSWORD_MAX_LENGTH} characters long.",
        )
    return value


def get_account_or_404(username):
    """Return the account with ``username`` or abort with 404."""
    account = Account.query.filter_by(username=username).first()
    if account is None:
        abort_json(404, f"Account '{username}' was not found.")
    return account

# ---------------------------------------------------------------------------
# Authentication resources (/api/auth)
# ---------------------------------------------------------------------------


@auth_ns.route("/login")
class LoginResource(Resource):
    """Public endpoint that exchanges credentials for a JWT access token."""

    @auth_ns.doc(
        security=[],
        description=(
            "Authenticates an account with `username` and `password` and "
            "returns a signed JWT access token valid for two hours. Send the "
            "token on every protected request as "
            "`Authorization: Bearer <access_token>`.\n\n"
            "The endpoint is public (no token required). Unknown usernames and "
            "wrong passwords return the **same** 401 response so that the API "
            "does not reveal which usernames exist. A correct password for a "
            "deactivated account returns 403, and every later request of that "
            "account fails with 403 as well, because the account is re-checked "
            "in the database on every request."
        ),
    )
    @auth_ns.expect(login_model, validate=False)
    @auth_ns.response(200, "Login succeeded.", token_model)
    @auth_ns.response(400, "Malformed request body.", error_model)
    @auth_ns.response(401, "Invalid username or password.", error_model)
    @auth_ns.response(403, "The account has been deactivated.", error_model)
    def post(self):
        """Log in and obtain a JWT access token."""
        payload = json_body("username", "password")
        username = payload.get("username")
        password = payload.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            abort_json(400, "Both 'username' and 'password' must be strings.")
        account = Account.query.filter_by(username=username.strip()).first()
        if account is None or not account.check_password(password):
            # Identical message for both cases: do not leak valid usernames.
            abort_json(401, "Invalid username or password.")
        if not account.is_active:
            # The password is checked first so a deactivated account cannot be
            # used to probe credentials.
            abort_json(403, "This account has been deactivated.")
        token = create_access_token(
            identity=account.username,
            additional_claims={"role": account.role},
        )
        return (
            {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
                "account": serialize_account(account),
            },
            200,
        )

# 当前账号：GET /api/auth/me
@auth_ns.route("/me")
class MeResource(Resource):
    """Return the account that belongs to the supplied access token."""

    @auth_ns.doc(
        security=JWT_SECURITY,
        description=(
            "Returns the public representation of the account behind the "
            "`Authorization: Bearer <token>` header. The account is loaded from "
            "the database, so the response always reflects the current `role` "
            "and `is_active` flags."
        ),
    )
    @auth_ns.response(200, "The authenticated account.", account_model)
    @auth_ns.response(401, "Missing, invalid or expired token.", error_model)
    @auth_ns.response(403, "The account has been deactivated.", error_model)
    @jwt_required()
    def get(self):
        """Show the authenticated account."""
        return serialize_account(current_account()), 200

# ---------------------------------------------------------------------------
# Account administration resources (/api/users), admin only
# ---------------------------------------------------------------------------


@users_ns.route("")
class UserListResource(Resource):
    """Collection endpoint for accounts: list and create."""

    @users_ns.doc(
        security=JWT_SECURITY,
        description=(
            "Returns a paginated list of all accounts. Optional filters: "
            "`is_active`, `role`, and `q` (case-insensitive substring match on "
            "the username). Results are ordered by `id` so paging is stable. "
            "Password hashes are **never** returned.\n\n"
            "Admin only."
        ),
        params={
            "page": {
                "description": "Page number, starting at 1.",
                "type": "integer",
                "default": 1,
            },
            "page_size": {
                "description": "Accounts per page, between 1 and 100.",
                "type": "integer",
                "default": DEFAULT_PAGE_SIZE,
            },
        },
    )
    @users_ns.expect(users_list_parser)
    @users_ns.response(200, "A page of accounts.", users_page_model)
    @users_ns.response(400, "Invalid query parameter.", error_model)
    @users_ns.response(401, "Missing, invalid or expired token.", error_model)
    @users_ns.response(403, "Admin privileges required.", error_model)
    @admin_required
    def get(self):
        """List accounts."""
        arguments = users_list_parser.parse_args()
        page, page_size = page_arguments()

        query = Account.query

        raw_is_active = arguments.get("is_active")
        if raw_is_active is not None:
            value = raw_is_active.strip().lower()
            if value in ("true", "1"):
                query = query.filter(Account.is_active.is_(True))
            elif value in ("false", "0"):
                query = query.filter(Account.is_active.is_(False))
            else:
                abort_json(400, "'is_active' must be 'true' or 'false'.")

        role = arguments.get("role")
        if role is not None:
            role = role.strip()
            if role not in ALLOWED_ROLES:
                abort_json(400, "'role' must be 'admin' or 'user'.")
            query = query.filter(Account.role == role)

        keyword = arguments.get("q")
        if keyword:
            # Escape LIKE wildcards so a search for "100%" is literal.
            escaped = (
                keyword.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            query = query.filter(Account.username.ilike(f"%{escaped}%", escape="\\"))

        total = query.count()
        rows = (
            query.order_by(Account.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [serialize_account(account) for account in rows]
        return paginated(items, page, page_size, total), 200

# 创建账号：POST /api/users
    @users_ns.doc(
        security=JWT_SECURITY,
        description=(
            "Creates a new **user** account. `username` must be 3-32 "
            "characters from `[A-Za-z0-9_.-]`; `password` must be 4-128 "
            "characters. The password is stored as a scrypt hash and never "
            "returned.\n\n"
            "A second administrator cannot be created: sending "
            '`"role": "admin"` returns 403. A duplicate username returns 409. '
            "Admin only."
        ),
    )
    @users_ns.expect(user_create_model, validate=False)
    @users_ns.response(201, "The account was created.", account_model)
    @users_ns.response(400, "Invalid username or password.", error_model)
    @users_ns.response(401, "Missing, invalid or expired token.", error_model)
    @users_ns.response(403, "Admin privileges required, or role=admin.", error_model)
    @users_ns.response(409, "The username is already taken.", error_model)
    @admin_required
    def post(self):
        """Create a user account."""
        payload = json_body("username", "password")
        username = validate_username(payload["username"])
        password = validate_password(payload["password"])

        role = payload.get("role", ROLE_USER)
        if not isinstance(role, str):
            abort_json(400, "'role' must be a string.")
        role = role.strip()
        if role == ROLE_ADMIN:
            abort_json(403, "Only one administrator account is allowed.")
        if role != ROLE_USER:
            abort_json(400, "'role' must be 'user'.")

        if Account.query.filter_by(username=username).first() is not None:
            abort_json(409, f"An account with username '{username}' already exists.")

        account = Account(username=username, role=ROLE_USER, is_active=True)
        account.set_password(password)
        try:
            db.session.add(account)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort_json(409, f"An account with username '{username}' already exists.")
        return (
            serialize_account(account),
            201,
            {"Location": f"/api/users/{account.username}"},
        )

# 账号详情：GET /api/users/{username}
@users_ns.route("/<string:username>")
class UserResource(Resource):
    """Item endpoint for one account: read, update and delete."""

    @users_ns.doc(
        security=JWT_SECURITY,
        description="Returns the public representation of one account. Admin only.",
    )
    @users_ns.response(200, "The account.", account_model)
    @users_ns.response(401, "Missing, invalid or expired token.", error_model)
    @users_ns.response(403, "Admin privileges required.", error_model)
    @users_ns.response(404, "The account does not exist.", error_model)
    @admin_required
    def get(self, username):
        """Show one account."""
        return serialize_account(get_account_or_404(username)), 200

    @users_ns.doc(
            security=JWT_SECURITY,
            description=(
                "Updates `is_active` and/or `password` of one account; at least one "
                "of the two fields must be present. Usernames and roles are "
                "immutable. The administrator account can never be deactivated "
                "(409). Deactivation takes effect immediately: the affected "
                "account's existing tokens stop working on the next request, and "
                "logging in returns 403. Admin only."
            ),
    )
    @users_ns.expect(user_update_model, validate=False)
    @users_ns.response(200, "The account was updated.", account_model)
    @users_ns.response(400, "Malformed or empty request body.", error_model)
    @users_ns.response(401, "Missing, invalid or expired token.", error_model)
    @users_ns.response(403, "Admin privileges required.", error_model)
    @users_ns.response(404, "The account does not exist.", error_model)
    @users_ns.response(
        409, "The administrator account cannot be deactivated.", error_model
    )
    @admin_required
    def patch(self, username):
        """Activate/deactivate an account or reset its password."""
        account = get_account_or_404(username)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort_json(400, "Request body must be a JSON object.")
        unsupported = sorted(set(payload) - {"is_active", "password"})
        if unsupported:
            abort_json(
                400,
                "Unsupported field(s): "
                f"{', '.join(unsupported)}. Only 'is_active' and 'password' "
                "can be modified.",
            )
        if not payload:
            abort_json(
                400,
                "Request body must contain at least one of 'is_active' or "
                "'password'.",
            )

        if "is_active" in payload:
            is_active = payload["is_active"]
            if not isinstance(is_active, bool):
                abort_json(400, "'is_active' must be a boolean.")
            if account.role == ROLE_ADMIN and is_active is False:
                abort_json(409, "The administrator account cannot be deactivated.")
            account.is_active = is_active

        if "password" in payload:
            account.set_password(validate_password(payload["password"]))

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort_json(409, "The account could not be updated.")
        return serialize_account(account), 200
    @users_ns.doc(
        security=JWT_SECURITY,
        description=(
            "Permanently deletes one account **and** all travel plans it "
            "created (the plan/route associations are removed with them). The "
            "administrator account cannot be deleted (409). Returns 204 with "
            "no body on success. Admin only."
        ),
    )
    @users_ns.response(204, "The account was deleted.")
    @users_ns.response(401, "Missing, invalid or expired token.", error_model)
    @users_ns.response(403, "Admin privileges required.", error_model)
    @users_ns.response(404, "The account does not exist.", error_model)
    @users_ns.response(409, "The administrator account cannot be deleted.", error_model)
    @admin_required
    def delete(self, username):
        """Delete a user account."""
        account = get_account_or_404(username)
        if account.role == ROLE_ADMIN:
            abort_json(409, "The administrator account cannot be deleted.")
        try:
            # Delete the plans explicitly so the plan_routes association rows
            # are removed before the account itself disappears.
            for plan in list(account.plans):
                db.session.delete(plan)
            db.session.delete(account)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort_json(
                409,
                "The account could not be deleted because related data still "
                "references it.",
            )
        return "", 204


# 账号相关的入口已经完整：两个种子账号都能登录，admin 能管理账号，
# 普通 user 碰不到任何管理接口。

# ---------------------------------------------------------------------------
# Importing airports, airlines and routes from CSV
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Constants, Swagger models and the upload parser
# ---------------------------------------------------------------------------

# Dataset order used in responses.
IMPORT_DATASETS = ("airports", "airlines", "routes")
# Write/delete order: always insert referenced rows before the rows that point
# at them, and delete the other way round.
IMPORT_APPLY_ORDER = ("airlines", "airports", "routes")
# Keep error payloads small: at most this many validation details are returned.
IMPORT_MAX_DETAILS = 20

IMPORT_COLUMNS = {
    "airlines": [
        "airline_id",
        "name",
        "iata_code",
        "icao_code",
        "country",
    ],
    "airports": [
        "airport_id",
        "name",
        "city",
        "country",
        "iata_code",
        "icao_code",
        "latitude",
        "longitude",
        "altitude",
        "timezone",
    ],
    "routes": [
        "route_id",
        "airline_id",
        "airline_iata",
        "origin_airport_id",
        "origin_iata",
        "destination_airport_id",
        "destination_iata",
        "codeshare",
        "stops",
        "equipment",
    ],
}

IMPORT_MODELS = {
    "airlines": Airline,
    "airports": Airport,
    "routes": Route,
}

# In-process record of the last successful import (used by GET /api/import/status).
import_last_run = {"at": None, "summary": None}

import_upload_parser = reqparse.RequestParser()
import_upload_parser.add_argument(
    "airports",
    type=reqparse.FileStorage,
    location="files",
    required=False,
    help=(
        "airports.csv - columns: airport_id,name,city,country,iata_code,"
        "icao_code,latitude,longitude,altitude,timezone"
    ),
)
import_upload_parser.add_argument(
    "airlines",
    type=reqparse.FileStorage,
    location="files",
    required=False,
    help="airlines.csv - columns: airline_id,name,iata_code,icao_code,country",
)
import_upload_parser.add_argument(
    "routes",
    type=reqparse.FileStorage,
    location="files",
    required=False,
    help=(
        "routes.csv - columns: route_id,airline_id,airline_iata,"
        "origin_airport_id,origin_iata,destination_airport_id,"
        "destination_iata,codeshare,stops,equipment"
    ),
)

import_counts_model = api.model(
    "ImportCounts",
    {
        "airports": fields.Integer(example=46),
        "airlines": fields.Integer(example=15),
        "routes": fields.Integer(example=260),
    },
)

import_result_model = api.model(
    "ImportResult",
    {
        "imported": fields.Nested(
            import_counts_model,
            description="Rows written, for each dataset included in the request.",
        ),
        "replaced": fields.List(
            fields.String,
            description="Datasets that were replaced by this request.",
            example=["airports", "airlines", "routes"],
        ),
        "counts": fields.Nested(
            import_counts_model,
            description="Rows stored in each table after the import.",
        ),
        "message": fields.String(example="Import completed successfully."),
    },
)

import_status_model = api.model(
    "ImportStatus",
    {
        "counts": fields.Nested(
            import_counts_model,
            description="Rows currently stored in each dataset table.",
        ),
        "last_import_at": fields.String(
            description=(
                "UTC timestamp of the most recent successful import in this "
                "server process, or null when nothing was imported yet."
            ),
            example="2026-10-26T02:30:00Z",
        ),
        "last_import": fields.Raw(
            description=(
                "Summary of the most recent successful import "
                "(`imported`, `replaced` and the resulting `counts`), or null."
            ),
        ),
    },
)

# ---------------------------------------------------------------------------
# Reading a CSV file and validating its schema
# ---------------------------------------------------------------------------


def import_detail(dataset, field, issue, row=None, route_id=None):
    """Build one machine-readable validation detail for the error envelope."""
    detail = {"dataset": dataset, "field": field, "issue": issue}
    if row is not None:
        detail["row"] = row
    if route_id is not None:
        detail["route_id"] = route_id
    return detail


def import_read_frame(dataset, upload):
    """Read one uploaded CSV into a dataframe of strings with validated headers.

    The file is parsed with ``header=None`` and ``dtype=str`` on purpose:
    pandas would otherwise treat a row with one field too many as an unnamed
    index column and silently shift every value. With ``header=None`` such a
    malformed row raises ``pandas.errors.ParserError`` instead.
    """
    payload = upload.read()
    if not payload:
        abort_json(
            400,
            f"The uploaded '{dataset}' file is empty.",
            details=[import_detail(dataset, "file", "the file has no content")],
        )
    try:
        frame = pd.read_csv(
            io.BytesIO(payload),
            header=None,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
    except (
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        ValueError,
    ) as error:
        abort_json(
            400,
            f"The uploaded '{dataset}' file could not be parsed as CSV.",
            details=[import_detail(dataset, "file", str(error))],
        )
    if frame.empty:
        abort_json(
            400,
            f"The uploaded '{dataset}' file is empty.",
            details=[import_detail(dataset, "file", "the file has no content")],
        )

    header = [str(column).strip() for column in frame.iloc[0].tolist()]
    expected = IMPORT_COLUMNS[dataset]
    missing = [column for column in expected if column not in header]
    unexpected = [column for column in header if column not in expected]
    if missing or unexpected or len(header) != len(expected):
        details = []
        if missing:
            details.append(
                import_detail(
                    dataset, "columns", "missing column(s): " + ", ".join(missing)
                )
            )
        if unexpected:
            details.append(
                import_detail(
                    dataset,
                    "columns",
                    "unexpected column(s): " + ", ".join(unexpected),
                )
            )
        if len(header) != len(expected) and not (missing or unexpected):
            details.append(
                import_detail(
                    dataset,
                    "columns",
                    f"expected {len(expected)} columns, found {len(header)}",
                )
            )
        abort_json(
            400,
            f"The uploaded '{dataset}' file does not match the expected schema.",
            details=details,
        )

    data = frame.iloc[1:].reset_index(drop=True)
    data.columns = header
    return data

# ---------------------------------------------------------------------------
# Cell level validators (one function per column type)
# ---------------------------------------------------------------------------


def import_parse_int(raw, dataset, field, row, errors, minimum=None):
    """Validate an integer cell and return the converted value (or None)."""
    text = raw.strip() if isinstance(raw, str) else ""
    if re.fullmatch(r"[+-]?[0-9]+", text) is None:
        errors.append(
            import_detail(dataset, field, "must be an integer", row=row)
        )
        return None
    value = int(text)
    if minimum is not None and value < minimum:
        errors.append(
            import_detail(
                dataset,
                field,
                f"must be greater than or equal to {minimum}",
                row=row,
            )
        )
        return None
    return value


def import_parse_float(raw, dataset, field, row, errors, minimum, maximum):
    """Validate a floating point cell inside an inclusive range."""
    text = raw.strip() if isinstance(raw, str) else ""
    try:
        value = float(text)
    except ValueError:
        errors.append(
            import_detail(
                dataset,
                field,
                f"must be a number between {minimum} and {maximum}",
                row=row,
            )
        )
        return None
    if not math.isfinite(value) or not minimum <= value <= maximum:
        errors.append(
            import_detail(
                dataset,
                field,
                f"must be a number between {minimum} and {maximum}",
                row=row,
            )
        )
        return None
    return value


def import_parse_text(raw, dataset, field, row, errors, max_length):
    """Validate a required, non-empty text cell."""
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        errors.append(
            import_detail(dataset, field, "must not be empty", row=row)
        )
        return None
    if len(text) > max_length:
        errors.append(
            import_detail(
                dataset,
                field,
                f"must be at most {max_length} characters",
                row=row,
            )
        )
        return None
    return text


def import_parse_code(raw, dataset, field, row, errors, length):
    """Validate an IATA/ICAO style code: exactly ``length`` uppercase letters."""
    text = raw.strip() if isinstance(raw, str) else ""
    if re.fullmatch(f"[A-Z]{{{length}}}", text) is None:
        errors.append(
            import_detail(
                dataset,
                field,
                f"must be {length} uppercase letters",
                row=row,
            )
        )
        return None
    return text


def import_check_unique(seen, value, dataset, field, row, errors):
    """Record ``value`` and report it when the same value occurs twice."""
    if value is None:
        return
    if value in seen:
        errors.append(
            import_detail(
                dataset,
                field,
                f"duplicate value '{value}' (first used at row {seen[value]})",
                row=row,
            )
        )
    else:
        seen[value] = row

# ---------------------------------------------------------------------------
# Per-dataset row validation
# ---------------------------------------------------------------------------


def import_validate_airlines(frame):
    """Validate every row of airlines.csv and return (rows, errors)."""
    rows, errors = [], []
    seen_ids, seen_iata, seen_icao = {}, {}, {}
    for row_number, record in enumerate(frame.to_dict("records"), start=2):
        airline_id = import_parse_int(
            record["airline_id"], "airlines", "airline_id", row_number, errors,
            minimum=1,
        )
        name = import_parse_text(
            record["name"], "airlines", "name", row_number, errors,
            max_length=120,
        )
        iata_code = import_parse_code(
            record["iata_code"], "airlines", "iata_code", row_number, errors, 2
        )
        icao_code = import_parse_code(
            record["icao_code"], "airlines", "icao_code", row_number, errors, 3
        )
        country = import_parse_text(
            record["country"], "airlines", "country", row_number, errors,
            max_length=64,
        )
        import_check_unique(
            seen_ids, airline_id, "airlines", "airline_id", row_number, errors
        )
        import_check_unique(
            seen_iata, iata_code, "airlines", "iata_code", row_number, errors
        )
        import_check_unique(
            seen_icao, icao_code, "airlines", "icao_code", row_number, errors
        )
        rows.append(
            {
                "airline_id": airline_id,
                "name": name,
                "iata_code": iata_code,
                "icao_code": icao_code,
                "country": country,
            }
        )
    return rows, errors


def import_validate_airports(frame):
    """Validate every row of airports.csv and return (rows, errors)."""
    rows, errors = [], []
    seen_ids, seen_iata, seen_icao = {}, {}, {}
    for row_number, record in enumerate(frame.to_dict("records"), start=2):
        airport_id = import_parse_int(
            record["airport_id"], "airports", "airport_id", row_number, errors,
            minimum=1,
        )
        name = import_parse_text(
            record["name"], "airports", "name", row_number, errors,
            max_length=160,
        )
        city = import_parse_text(
            record["city"], "airports", "city", row_number, errors,
            max_length=80,
        )
        country = import_parse_text(
            record["country"], "airports", "country", row_number, errors,
            max_length=80,
        )
        iata_code = import_parse_code(
            record["iata_code"], "airports", "iata_code", row_number, errors, 3
        )
        icao_code = import_parse_code(
            record["icao_code"], "airports", "icao_code", row_number, errors, 4
        )
        latitude = import_parse_float(
            record["latitude"], "airports", "latitude", row_number, errors,
            -90.0, 90.0,
        )
        longitude = import_parse_float(
            record["longitude"], "airports", "longitude", row_number, errors,
            -180.0, 180.0,
        )
        altitude = import_parse_int(
            record["altitude"], "airports", "altitude", row_number, errors
        )
        timezone = import_parse_text(
            record["timezone"], "airports", "timezone", row_number, errors,
            max_length=64,
        )
        import_check_unique(
            seen_ids, airport_id, "airports", "airport_id", row_number, errors
        )
        import_check_unique(
            seen_iata, iata_code, "airports", "iata_code", row_number, errors
        )
        import_check_unique(
            seen_icao, icao_code, "airports", "icao_code", row_number, errors
        )
        rows.append(
            {
                "airport_id": airport_id,
                "name": name,
                "city": city,
                "country": country,
                "iata_code": iata_code,
                "icao_code": icao_code,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "timezone": timezone,
            }
        )
    return rows, errors

def import_validate_routes(frame):
    """Validate every row of routes.csv and return (rows, errors)."""
    rows, errors = [], []
    seen_ids = {}
    for row_number, record in enumerate(frame.to_dict("records"), start=2):
        route_id = import_parse_int(
            record["route_id"], "routes", "route_id", row_number, errors,
            minimum=1,
        )
        airline_id = import_parse_int(
            record["airline_id"], "routes", "airline_id", row_number, errors,
            minimum=1,
        )
        airline_iata = import_parse_code(
            record["airline_iata"], "routes", "airline_iata", row_number,
            errors, 2,
        )
        origin_airport_id = import_parse_int(
            record["origin_airport_id"], "routes", "origin_airport_id",
            row_number, errors, minimum=1,
        )
        origin_iata = import_parse_code(
            record["origin_iata"], "routes", "origin_iata", row_number,
            errors, 3,
        )
        destination_airport_id = import_parse_int(
            record["destination_airport_id"], "routes",
            "destination_airport_id", row_number, errors, minimum=1,
        )
        destination_iata = import_parse_code(
            record["destination_iata"], "routes", "destination_iata",
            row_number, errors, 3,
        )
        stops = import_parse_int(
            record["stops"], "routes", "stops", row_number, errors, minimum=0
        )

        codeshare = record["codeshare"].strip() if isinstance(
            record["codeshare"], str
        ) else ""
        if codeshare == "":
            codeshare = None
        elif codeshare not in ("Y", "N"):
            errors.append(
                import_detail(
                    "routes",
                    "codeshare",
                    "must be empty, 'Y' or 'N'",
                    row=row_number,
                )
            )
            codeshare = None

        equipment = record["equipment"].strip() if isinstance(
            record["equipment"], str
        ) else ""
        if len(equipment) > 20:
            errors.append(
                import_detail(
                    "routes",
                    "equipment",
                    "must be at most 20 characters",
                    row=row_number,
                )
            )
            equipment = None
        elif equipment == "":
            equipment = None

        import_check_unique(
            seen_ids, route_id, "routes", "route_id", row_number, errors
        )
        rows.append(
            {
                "route_id": route_id,
                "airline_id": airline_id,
                "airline_iata": airline_iata,
                "origin_airport_id": origin_airport_id,
                "origin_iata": origin_iata,
                "destination_airport_id": destination_airport_id,
                "destination_iata": destination_iata,
                "codeshare": codeshare,
                "stops": stops,
                "equipment": equipment,
                "_row": row_number,
            }
        )
    return rows, errors


IMPORT_VALIDATORS = {
    "airlines": import_validate_airlines,
    "airports": import_validate_airports,
    "routes": import_validate_routes,
}

# ---------------------------------------------------------------------------
# Merged-data checks: consistency, referential integrity, plan safety
# ---------------------------------------------------------------------------
# 合并视图（merged view）是什么？
#
# 一次请求里同时上传多个文件时，完整性必须针对"合并后的结果"检查，
# 而不是只针对数据库里现有的数据。
#
# 举例：数据库里现在有 15 家航司；本次请求上传了新的 airlines.csv（只含 3 家）
# 和一份 routes.csv（引用了第 4 家）。合并后的状态是"3 家航司 + 这批新航线"，
# 第 4 家不存在，必须拒绝（409）。如果只看数据库现有数据，反而会误判为存在。
#
# 做法：先取数据库现状，再用请求里上传的数据集覆盖对应部分，得到 merged_*，
# 然后只检查这个合并结果。

def import_stored_reference_data():
    """Return ``(airline_iata, airport_iata)`` mappings from the database."""
    airline_iata = {
        airline.airline_id: airline.iata_code
        for airline in db.session.query(Airline).all()
    }
    airport_iata = {
        airport.airport_id: airport.iata_code
        for airport in db.session.query(Airport).all()
    }
    return airline_iata, airport_iata


def import_stored_route_rows():
    """Return the stored routes as plain dictionaries."""
    rows = []
    for route in db.session.query(Route).order_by(Route.route_id).all():
        rows.append(
            {
                "route_id": route.route_id,
                "airline_id": route.airline_id,
                "airline_iata": route.airline_iata,
                "origin_airport_id": route.origin_airport_id,
                "origin_iata": route.origin_iata,
                "destination_airport_id": route.destination_airport_id,
                "destination_iata": route.destination_iata,
                "codeshare": route.codeshare,
                "stops": route.stops,
                "equipment": route.equipment,
            }
        )
    return rows


def import_check_references(route_rows, airline_iata, airport_iata):
    """Check the merged route set against the merged reference data.

    Returns ``(consistency_issues, integrity_issues)``.

    一致性错误（400）表示请求自身自相矛盾：例如 origin_iata='LAX'，但
    origin_airport_id=1 实际是 SYD。引用缺失（409）表示文件本身没问题，但它
    与系统当前状态冲突（引用的航司/机场不存在，或改动会破坏已有计划），
    这正是 HTTP 409 Conflict 的语义。

    * ``consistency_issues`` - the denormalised IATA code does not match the
      airline/airport that the numeric id points at (a 400 data error).
    * ``integrity_issues`` - the numeric id points at nothing at all
      (a 409 referential integrity error).
    """
    consistency, integrity = [], []
    references = (
        ("airline_id", "airline_iata", airline_iata),
        ("origin_airport_id", "origin_iata", airport_iata),
        ("destination_airport_id", "destination_iata", airport_iata),
    )
    for route in route_rows:
        row_number = route.get("_row")
        for id_field, iata_field, reference_map in references:
            reference_id = route[id_field]
            expected_iata = reference_map.get(reference_id)
            if expected_iata is None:
                integrity.append(
                    {
                        "route_id": route["route_id"],
                        "field": id_field,
                        "value": reference_id,
                        "row": row_number,
                    }
                )
                continue
            if route[iata_field] != expected_iata:
                consistency.append(
                    import_detail(
                        "routes",
                        iata_field,
                        f"route {route['route_id']}: {iata_field} "
                        f"'{route[iata_field]}' does not match iata_code "
                        f"'{expected_iata}' of {id_field}={reference_id}",
                        row=row_number,
                        route_id=route["route_id"],
                    )
                )
    return consistency, integrity


def import_integrity_message(integrity, airline_iata, airport_iata):
    """Build the 409 message, quoting at most three concrete violations."""
    examples = [
        f"Route {violation['route_id']} references {violation['field']}="
        f"{violation['value']} which does not exist."
        for violation in integrity[:3]
    ]
    message = "Import rejected: referential integrity check failed. " + " ".join(
        examples
    )
    if not airline_iata:
        message += (
            " The airlines dataset is empty: import airlines.csv in the same "
            "request or import it first."
        )
    if not airport_iata:
        message += (
            " The airports dataset is empty: import airports.csv in the same "
            "request or import it first."
        )
    return message


def import_integrity_details(integrity):
    """Render the integrity violations as error details."""
    return [
        import_detail(
            "routes",
            violation["field"],
            f"route {violation['route_id']} references "
            f"{violation['field']}={violation['value']} which does not exist",
            row=violation["row"],
            route_id=violation["route_id"],
        )
        for violation in integrity[:IMPORT_MAX_DETAILS]
    ]

# 计划保护：为什么不"自动清理"受影响的计划？
#
# 替换 routes 会删掉旧航线，而用户的旅行计划可能正引用它们。可以选择拒绝
# 导入、接受并标记受影响的计划，或者静默丢弃引用；本实现选择拒绝 409 并列出
# 受影响的计划名，理由是：
#
# - 用户数据（旅行计划）不应该因为一次后台数据刷新而静默丢失；
# - 409 让管理员明确知道"先让这些用户调整计划"，把决策权交还给人；
# - 相比"接受并标记"，实现简单、状态一致，不会留下"半有效"的计划。
def import_affected_plans(new_route_ids):
    """Return (plan_count, plan_names) for plans that would lose a route."""
    references = (
        db.session.query(plan_routes.c.route_id, TravelPlan.plan_id, TravelPlan.name)
        .join(TravelPlan, TravelPlan.plan_id == plan_routes.c.plan_id)
        .order_by(TravelPlan.plan_id, plan_routes.c.route_id)
        .all()
    )
    removed = [
        reference
        for reference in references
        if reference.route_id not in new_route_ids
    ]
    plan_names = []
    for reference in removed:
        if reference.name not in plan_names:
            plan_names.append(reference.name)
    return len({reference.plan_id for reference in removed}), plan_names
# ---------------------------------------------------------------------------
# Database write helpers
# ---------------------------------------------------------------------------


def import_model_rows(dataset, rows):
    """Drop helper keys (such as ``_row``) and keep only model columns."""
    columns = IMPORT_COLUMNS[dataset]
    return [{column: row[column] for column in columns} for row in rows]


def import_table_counts():
    """Return the number of rows currently stored for each dataset."""
    return {
        "airports": db.session.query(Airport).count(),
        "airlines": db.session.query(Airline).count(),
        "routes": db.session.query(Route).count(),
    }


def import_replace_datasets(uploaded):
    """Replace the uploaded datasets inside one database transaction.

    Deletion runs child-first and insertion parent-first. Every failure rolls
    the whole transaction back, so the database is either fully updated or
    completely untouched.
    """
    try:
        for dataset in reversed(IMPORT_APPLY_ORDER):
            if dataset in uploaded:
                db.session.query(IMPORT_MODELS[dataset]).delete(
                    synchronize_session=False
                )
        for dataset in IMPORT_APPLY_ORDER:
            if dataset in uploaded:
                db.session.bulk_insert_mappings(
                    IMPORT_MODELS[dataset],
                    import_model_rows(dataset, uploaded[dataset]),
                )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort_json(
            409,
            "Import rejected: the data violates a database constraint.",
        )
    except SQLAlchemyError:
        db.session.rollback()
        abort_json(
            500,
            "Import failed while writing to the database. No data was changed.",
        )

# ---------------------------------------------------------------------------
# Import resources (/api/import), admin only
# ---------------------------------------------------------------------------


@import_ns.route("")
class ImportResource(Resource):
    """Upload one or more of the three CSV datasets."""

    @import_ns.doc(
        security=JWT_SECURITY,
        description=(
            "Uploads one or more CSV datasets as `multipart/form-data` file "
            "parts named `airports`, `airlines` and `routes`. **At least one "
            "file is required** and any subset of the three datasets can be "
            "sent; datasets that are not part of the request are left "
            "completely untouched.\n\n"
            "### Replace semantics\n"
            "A dataset included in the request **replaces** all rows currently "
            "stored for that dataset. The request is validated as a whole "
            "before the database is touched and is applied in a single "
            "transaction, so a rejected request never changes any data.\n\n"
            "### Validation layers\n"
            "1. **File shape (400)** - the CSV must be parseable and contain "
            "exactly the expected column set (order does not matter). Expected "
            "columns: `airlines`: airline_id,name,iata_code,icao_code,country; "
            "`airports`: airport_id,name,city,country,iata_code,icao_code,"
            "latitude,longitude,altitude,timezone; `routes`: route_id,"
            "airline_id,airline_iata,origin_airport_id,origin_iata,"
            "destination_airport_id,destination_iata,codeshare,stops,"
            "equipment.\n"
            "2. **Cell values (400)** - numeric columns must be integers / "
            "numbers in range, IATA codes must be 2 or 3 uppercase letters, "
            "ICAO codes 3 or 4 uppercase letters, identifiers must be "
            "positive and unique inside the file, `stops >= 0` and `codeshare` "
            "must be empty, `Y` or `N`.\n"
            "3. **Cross-field consistency (400)** - a route's `airline_iata`, "
            "`origin_iata` and `destination_iata` must equal the IATA code of "
            "the airline/airport referenced by the corresponding numeric id. "
            "The reference data is the uploaded dataset when it is part of "
            "this request, otherwise the data already stored.\n"
            "4. **Referential integrity (409)** - after applying every "
            "uploaded file, no route may reference an airline or airport that "
            "does not exist. This is checked against the **combined** result "
            "of the request, so uploading all three files together succeeds "
            "even on an empty database.\n"
            "5. **Existing travel plans (409)** - replacing `routes` may remove "
            "routes that an existing travel plan refers "
            "to. Rather than silently breaking or shrinking a user's plan, the "
            "whole import is rejected: `Import rejected: N travel plan(s) "
            "reference routes that would be removed.` The `details` list names "
            "up to five affected plans. Routes that keep their `route_id` may "
            "change their attributes safely, so refreshing the same routes "
            "dataset is always allowed.\n\n"
            "Admin only."
        ),
    )
    @import_ns.expect(import_upload_parser)
    @import_ns.response(200, "Import completed successfully.", import_result_model)
    @import_ns.response(400, "Missing, malformed or invalid CSV file.", error_model)
    @import_ns.response(401, "Missing, invalid or expired token.", error_model)
    @import_ns.response(403, "Admin privileges required.", error_model)
    @import_ns.response(
        409,
        "Referential integrity check failed, or travel plans would break.",
        error_model,
    )
    @admin_required
    def post(self):
        """Import airports, airlines and routes from CSV files."""
        # -- 1. Collect the uploaded files (empty browser file inputs count as
        #       "not uploaded").
        arguments = import_upload_parser.parse_args()
        uploads = {}
        for dataset in IMPORT_DATASETS:
            upload = arguments.get(dataset)
            if upload is not None and getattr(upload, "filename", ""):
                uploads[dataset] = upload
        if not uploads:
            abort_json(
                400,
                "At least one of the 'airports', 'airlines' or 'routes' CSV "
                "files must be uploaded.",
            )

        # -- 2. Read and validate the uploaded files. Nothing is written here.
        uploaded = {}
        validation_errors = []
        for dataset in IMPORT_DATASETS:
            if dataset not in uploads:
                continue
            frame = import_read_frame(dataset, uploads[dataset])
            rows, errors = IMPORT_VALIDATORS[dataset](frame)
            uploaded[dataset] = rows
            validation_errors.extend(errors)
        if validation_errors:
            details = validation_errors[:IMPORT_MAX_DETAILS]
            if len(validation_errors) > IMPORT_MAX_DETAILS:
                details.append(
                    import_detail(
                        "file",
                        "summary",
                        f"{len(validation_errors)} validation issue(s) found; "
                        f"showing the first {IMPORT_MAX_DETAILS}.",
                    )
                )
            abort_json(
                400,
                "File validation failed. No data was changed.",
                details=details,
            )

        # -- 3. Build the merged view: an uploaded dataset overrides the
        #       currently stored rows of that dataset.
        merged_airline_iata, merged_airport_iata = import_stored_reference_data()
        merged_routes = import_stored_route_rows()
        if "airlines" in uploaded:
            merged_airline_iata = {
                row["airline_id"]: row["iata_code"] for row in uploaded["airlines"]
            }
        if "airports" in uploaded:
            merged_airport_iata = {
                row["airport_id"]: row["iata_code"] for row in uploaded["airports"]
            }
        if "routes" in uploaded:
            merged_routes = list(uploaded["routes"])

        # -- 4. Consistency of the denormalised IATA columns (400) and
        #       referential integrity of the merged result (409).
        consistency_issues, integrity_issues = import_check_references(
            merged_routes, merged_airline_iata, merged_airport_iata
        )
        if consistency_issues:
            abort_json(
                400,
                "File validation failed: route data is inconsistent with the "
                "referenced airlines or airports.",
                details=consistency_issues[:IMPORT_MAX_DETAILS],
            )
        if integrity_issues:
            abort_json(
                409,
                import_integrity_message(
                    integrity_issues, merged_airline_iata, merged_airport_iata
                ),
                details=import_integrity_details(integrity_issues),
            )

        # -- 5. Replacing routes must not break existing travel plans.
        if "routes" in uploaded:
            new_route_ids = {row["route_id"] for row in uploaded["routes"]}
            affected_count, affected_names = import_affected_plans(new_route_ids)
            if affected_count:
                abort_json(
                    409,
                    f"Import rejected: {affected_count} travel plan(s) "
                    "reference routes that would be removed.",
                    details=[
                        import_detail(
                            "routes",
                            "plan",
                            f"travel plan '{name}' references routes that would "
                            "be removed",
                        )
                        for name in affected_names[:5]
                    ],
                )

        # -- 6. Apply the import: delete + bulk insert in one transaction.
        replaced = [dataset for dataset in IMPORT_DATASETS if dataset in uploaded]
        imported = {dataset: len(uploaded[dataset]) for dataset in replaced}
        import_replace_datasets(uploaded)
        counts = import_table_counts()
        import_last_run["at"] = utcnow()
        import_last_run["summary"] = {
            "imported": imported,
            "replaced": replaced,
            "counts": counts,
        }
        return (
            {
                "imported": imported,
                "replaced": replaced,
                "counts": counts,
                "message": "Import completed successfully.",
            },
            200,
        )


@import_ns.route("/status")
class ImportStatusResource(Resource):
    """Small self-check endpoint showing what the database currently holds."""

    @import_ns.doc(
        security=JWT_SECURITY,
        description=(
            "Returns the number of rows currently stored for airports, "
            "airlines and routes, plus the UTC timestamp and summary of the "
            "most recent successful import handled by this server process. "
            "Useful to verify that a rejected import did not change anything. "
            "Admin only."
        ),
    )
    @import_ns.response(200, "Current dataset sizes.", import_status_model)
    @import_ns.response(401, "Missing, invalid or expired token.", error_model)
    @import_ns.response(403, "Admin privileges required.", error_model)
    @admin_required
    def get(self):
        """Show current dataset sizes and the latest import."""
        return (
            {
                "counts": import_table_counts(),
                "last_import_at": iso_utc(import_last_run["at"]),
                "last_import": import_last_run["summary"],
            },
            200,
        )

# ---------------------------------------------------------------------------
# Exploring airports, airlines and routes
# ---------------------------------------------------------------------------
#
# Everything below is read-only and available to every authenticated, active
# account (an admin browses exactly like an ordinary user).  The public
# identifier of an airport and of an airline is its IATA code instead of the
# surrogate integer primary key: IATA codes are what humans type, they are
# unique in the dataset, and they survive a re-import of the CSV files, whereas
# `airport_id` / `route_id` are only meaningful inside one particular import.
#
# The resources are shaped around the three entities (airports, airlines,
# routes) and are linked to each other through sub-resources and `_links`
# objects, so a client can navigate the graph without knowing SQLite internals.

EXPLORE_FUZZY_CUTOFF = 60.0
EXPLORE_AIRLINE_CODE_RE = re.compile(r"^[A-Za-z]{2}$")
EXPLORE_AIRPORT_CODE_RE = re.compile(r"^[A-Za-z]{3}$")
EXPLORE_DIRECTIONS = ("departure", "arrival", "both")

airport_page_model = collection_model("AirportPage", airport_model)
airline_page_model = collection_model("AirlinePage", airline_model)
route_page_model = collection_model("RoutePage", route_model)

airport_detail_model = api.model(
    "AirportDetail",
    {
        "airport_id": fields.Integer(example=1),
        "name": fields.String(example="Sydney Kingsford Smith Airport"),
        "city": fields.String(example="Sydney"),
        "country": fields.String(example="Australia"),
        "iata_code": fields.String(example="SYD"),
        "icao_code": fields.String(example="YSSY"),
        "latitude": fields.Float(example=-33.9461),
        "longitude": fields.Float(example=151.1772),
        "altitude": fields.Integer(example=6),
        "timezone": fields.String(example="Australia/Sydney"),
        "route_count": fields.Integer(
            description="Departing plus arriving routes.", example=48
        ),
        "departure_route_count": fields.Integer(example=24),
        "arrival_route_count": fields.Integer(example=24),
        "airline_count": fields.Integer(
            description="Distinct airlines serving the airport.", example=12
        ),
        "_links": fields.Raw,
    },
)

airline_detail_model = api.model(
    "AirlineDetail",
    {
        "airline_id": fields.Integer(example=1),
        "name": fields.String(example="Qantas"),
        "iata_code": fields.String(example="QF"),
        "icao_code": fields.String(example="QFA"),
        "country": fields.String(example="Australia"),
        "route_count": fields.Integer(
            description="Routes operated by the airline.", example=42
        ),
        "airport_count": fields.Integer(
            description="Distinct airports served by the airline.", example=18
        ),
        "_links": fields.Raw,
    },
)

EXPLORE_PAGE_PARAMS = {
    "page": {
        "in": "query",
        "type": "integer",
        "default": 1,
        "minimum": 1,
        "description": "1-based page number.",
    },
    "page_size": {
        "in": "query",
        "type": "integer",
        "default": DEFAULT_PAGE_SIZE,
        "minimum": 1,
        "maximum": MAX_PAGE_SIZE,
        "description": f"Items per page (1-{MAX_PAGE_SIZE}).",
    },
}

def explore_bool_arg(name):
    """Read an optional boolean query flag such as ``fuzzy`` or ``expand``."""
    raw = request.args.get(name)
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in ("true", "1", "yes", "y"):
        return True
    if value in ("false", "0", "no", "n", ""):
        return False
    abort_json(400, f"'{name}' must be a boolean: true or false.")


def explore_code_arg(name, pattern, label):
    """Read and upper-case an optional IATA code query parameter.

    A malformed code is a client error (400).  A well formed code that simply
    does not occur in the data is *not* an error: the collection endpoint then
    answers with an empty page (200), so a client can tell "I typed the
    parameter wrong" apart from "this code has no matches".
    """
    raw = request.args.get(name)
    if raw is None or not raw.strip():
        return None
    value = raw.strip().upper()
    if not pattern.match(value):
        abort_json(400, f"'{name}' must be a {label} IATA code.")
    return value


def explore_like_pattern(term):
    """Escape ``%``/``_`` and wrap a free-text term in a ``LIKE`` pattern.

    Without the escaping a user could send ``q=%`` and match every row, which
    makes the API's behaviour depend on characters that are supposed to be
    ordinary text.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def explore_fuzzy_rank(rows, term):
    """Order ``rows`` by fuzzy similarity of their name to ``term``.

    ``rapidfuzz.process.extract`` returns ``(choice, score, index)`` tuples in
    descending ``WRatio`` order; ``index`` is the position in the ``choices``
    list we pass in, so it maps straight back to the ORM row.  Matches below
    ``EXPLORE_FUZZY_CUTOFF`` are dropped as noise: without a cut-off even
    ``zzz`` would "match" the whole catalogue with a score of 0.
    """
    choices = [row.name for row in rows]
    ranked = []
    for _choice, score, index in rapidfuzz_process.extract(
        term, choices, scorer=rapidfuzz_fuzz.WRatio, limit=None
    ):
        if score >= EXPLORE_FUZZY_CUTOFF:
            ranked.append(rows[index])
    return ranked


def explore_page_slice(items, page, page_size):
    """Slice an in-memory (already ordered) list for the pagination envelope."""
    start = (page - 1) * page_size
    return items[start : start + page_size]


def explore_airport_or_404(iata):
    """Resolve a case-insensitive IATA code to an airport or abort with 404."""
    airport = Airport.query.filter(
        func.lower(Airport.iata_code) == iata.strip().lower()
    ).first()
    if airport is None:
        abort_json(404, f"Airport '{iata.strip().upper()}' was not found.")
    return airport


def explore_airline_or_404(iata):
    """Resolve a case-insensitive IATA code to an airline or abort with 404."""
    airline = Airline.query.filter(
        func.lower(Airline.iata_code) == iata.strip().lower()
    ).first()
    if airline is None:
        abort_json(404, f"Airline '{iata.strip().upper()}' was not found.")
    return airline


def explore_direction():
    """Validate the ``direction`` filter of the airport routes sub-resource."""
    direction = request.args.get("direction", "both").strip().lower() or "both"
    if direction not in EXPLORE_DIRECTIONS:
        abort_json(400, "'direction' must be one of: departure, arrival, both.")
    return direction


def explore_airport_airlines(airport_id):
    """Distinct airlines operating to/from ``airport_id``, ordered by id."""
    routes = Route.query.filter(
        or_(
            Route.origin_airport_id == airport_id,
            Route.destination_airport_id == airport_id,
        )
    ).all()
    return sorted(
        unique([route.airline for route in routes]),
        key=lambda airline: airline.airline_id,
    )


def explore_airport_destinations(airport_id):
    """Distinct airports reachable from ``airport_id`` by a direct flight."""
    routes = Route.query.filter(Route.origin_airport_id == airport_id).all()
    return sorted(
        unique([route.destination for route in routes]),
        key=lambda airport: airport.airport_id,
    )


def explore_airport_airline_count(airport_id):
    """Number of distinct airlines serving an airport (either direction)."""
    departures = db.session.query(Route.airline_id).filter(
        Route.origin_airport_id == airport_id
    )
    arrivals = db.session.query(Route.airline_id).filter(
        Route.destination_airport_id == airport_id
    )
    return departures.union(arrivals).count()


def explore_airline_airport_count(airline_id):
    """Number of distinct airports an airline serves (either direction)."""
    origins = db.session.query(Route.origin_airport_id).filter(
        Route.airline_id == airline_id
    )
    destinations = db.session.query(Route.destination_airport_id).filter(
        Route.airline_id == airline_id
    )
    return origins.union(destinations).count()

@airports_ns.route("")
class AirportListResource(Resource):
    """Browse the airport catalogue with filtering, fuzzy search and paging."""

    @airports_ns.doc(
        description=(
            "Return a paginated page of airports. Available to **any active "
            "account** (admin or user).\n\n"
            "**Filters** (all combine with AND):\n"
            "* `q` - case-insensitive substring match over `name`, `city`, "
            "`country`, `iata_code` and `icao_code`.\n"
            "* `country`, `city` - exact match, case-insensitive.\n"
            "* `iata_code` - exact match, case-insensitive.\n\n"
            "**Fuzzy search**: add `fuzzy=true` to rank the `q` term against the "
            "airport `name` with RapidFuzz `WRatio` similarity instead of doing "
            "substring matching, which tolerates typos (`Sydny` still finds "
            "`SYD`). It requires a `q` value and drops matches below a "
            "similarity cut-off as noise.\n\n"
            "Results are ordered by `airport_id`; fuzzy results are ordered by "
            "descending similarity."
        ),
        security=[JWT_SECURITY],
        params={
            **EXPLORE_PAGE_PARAMS,
            "q": {
                "in": "query",
                "type": "string",
                "description": "Free-text search term (case-insensitive substring).",
            },
            "country": {
                "in": "query",
                "type": "string",
                "description": "Exact country name, case-insensitive.",
            },
            "city": {
                "in": "query",
                "type": "string",
                "description": "Exact city name, case-insensitive.",
            },
            "iata_code": {
                "in": "query",
                "type": "string",
                "description": "Exact IATA code, case-insensitive.",
            },
            "fuzzy": {
                "in": "query",
                "type": "boolean",
                "default": False,
                "description": "Rank the `q` matches by fuzzy name similarity.",
            },
        },
    )
    @airports_ns.response(200, "A page of airports", airport_page_model)
    @airports_ns.response(400, "Invalid query parameter", error_model)
    @airports_ns.response(401, "Missing, invalid or expired token", error_model)
    @jwt_required()
    def get(self):
        """List and search airports."""
        current_account()
        page, page_size = page_arguments()

        query = Airport.query
        term = request.args.get("q", "").strip()
        country = (request.args.get("country") or "").strip()
        city = (request.args.get("city") or "").strip()
        iata_code = (request.args.get("iata_code") or "").strip()
        fuzzy = explore_bool_arg("fuzzy")

        if country:
            query = query.filter(func.lower(Airport.country) == country.lower())
        if city:
            query = query.filter(func.lower(Airport.city) == city.lower())
        if iata_code:
            query = query.filter(func.lower(Airport.iata_code) == iata_code.lower())

        if not term:
            if fuzzy:
                abort_json(400, "'fuzzy=true' requires a 'q' search term.")
            total = query.count()
            rows = (
                query.order_by(Airport.airport_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return paginated(
                [serialize_airport(airport) for airport in rows],
                page,
                page_size,
                total,
            )

        if fuzzy:
            # Fuzzy ranking happens in Python because the score is computed by
            # RapidFuzz, not by SQLite.  The dataset is tiny (a few dozen rows),
            # so loading the filtered candidates is cheap; a production system
            # with millions of rows would move this into a search index.
            ranked = explore_fuzzy_rank(query.order_by(Airport.airport_id).all(), term)
            rows = explore_page_slice(ranked, page, page_size)
            return paginated(
                [serialize_airport(airport) for airport in rows],
                page,
                page_size,
                len(ranked),
            )

        pattern = explore_like_pattern(term)
        query = query.filter(
            or_(
                Airport.name.ilike(pattern, escape="\\"),
                Airport.city.ilike(pattern, escape="\\"),
                Airport.country.ilike(pattern, escape="\\"),
                Airport.iata_code.ilike(pattern, escape="\\"),
                Airport.icao_code.ilike(pattern, escape="\\"),
            )
        )
        total = query.count()
        rows = (
            query.order_by(Airport.airport_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return paginated(
            [serialize_airport(airport) for airport in rows], page, page_size, total
        )


@airports_ns.route("/<string:iata>")
class AirportResource(Resource):
    """Airport detail plus the route statistics a client needs to navigate."""

    @airports_ns.doc(
        description=(
            "Look up a single airport by IATA code (case-insensitive) and get "
            "the statistics needed to decide what to explore next, without "
            "knowing the database schema:\n"
            "* `route_count` - departing plus arriving routes;\n"
            "* `departure_route_count` / `arrival_route_count`;\n"
            "* `airline_count` - distinct airlines serving the airport.\n\n"
            "The `_links` object points at the `/routes`, `/airlines` and "
            "`/destinations` sub-resources. Available to any active account."
        ),
        security=[JWT_SECURITY],
    )
    @airports_ns.response(200, "The airport", airport_detail_model)
    @airports_ns.response(401, "Missing, invalid or expired token", error_model)
    @airports_ns.response(404, "Airport not found", error_model)
    @jwt_required()
    def get(self, iata):
        """Airport detail with route statistics."""
        current_account()
        airport = explore_airport_or_404(iata)

        departure_count = Route.query.filter(
            Route.origin_airport_id == airport.airport_id
        ).count()
        arrival_count = Route.query.filter(
            Route.destination_airport_id == airport.airport_id
        ).count()

        data = serialize_airport(airport)
        data["route_count"] = departure_count + arrival_count
        data["departure_route_count"] = departure_count
        data["arrival_route_count"] = arrival_count
        data["airline_count"] = explore_airport_airline_count(airport.airport_id)
        data["_links"]["destinations"] = (
            f"/api/airports/{airport.iata_code}/destinations"
        )
        return data


@airports_ns.route("/<string:iata>/routes")
class AirportRoutesResource(Resource):
    """The routes that touch an airport, filterable by travel direction."""

    @airports_ns.doc(
        description=(
            "Return the routes that touch an airport.\n\n"
            "* `direction=departure` - routes whose **origin** is this airport;\n"
            "* `direction=arrival` - routes whose **destination** is this "
            "airport;\n"
            "* `direction=both` (default) - either of the two.\n\n"
            "Routes are returned as compact summaries (IATA codes plus `_links` "
            "to the airline and both airports) to keep the page small; call "
            "`GET /api/routes/{route_id}` for the expanded representation. "
            "Available to any active account."
        ),
        security=[JWT_SECURITY],
        params={
            **EXPLORE_PAGE_PARAMS,
            "direction": {
                "in": "query",
                "type": "string",
                "enum": ["departure", "arrival", "both"],
                "default": "both",
                "description": "Which side of the route must touch the airport.",
            },
        },
    )
    @airports_ns.response(200, "A page of routes", route_page_model)
    @airports_ns.response(400, "Invalid query parameter", error_model)
    @airports_ns.response(401, "Missing, invalid or expired token", error_model)
    @airports_ns.response(404, "Airport not found", error_model)
    @jwt_required()
    def get(self, iata):
        """Routes departing from or arriving at an airport."""
        current_account()
        airport = explore_airport_or_404(iata)
        page, page_size = page_arguments()
        direction = explore_direction()

        query = Route.query
        if direction == "departure":
            query = query.filter(Route.origin_airport_id == airport.airport_id)
        elif direction == "arrival":
            query = query.filter(Route.destination_airport_id == airport.airport_id)
        else:
            query = query.filter(
                or_(
                    Route.origin_airport_id == airport.airport_id,
                    Route.destination_airport_id == airport.airport_id,
                )
            )

        total = query.count()
        rows = (
            query.order_by(Route.route_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return paginated(
            [serialize_route(route) for route in rows], page, page_size, total
        )


@airports_ns.route("/<string:iata>/airlines")
class AirportAirlinesResource(Resource):
    """The airlines that operate at an airport, de-duplicated."""

    @airports_ns.doc(
        description=(
            "Return the distinct airlines that operate at least one route to or "
            "from the airport. An airline usually serves an airport in both "
            "directions, so a naive join would list it twice - the result is "
            "de-duplicated so each airline appears exactly once.\n\n"
            "Available to any active account."
        ),
        security=[JWT_SECURITY],
        params={**EXPLORE_PAGE_PARAMS},
    )
    @airports_ns.response(200, "A page of airlines", airline_page_model)
    @airports_ns.response(400, "Invalid pagination parameter", error_model)
    @airports_ns.response(401, "Missing, invalid or expired token", error_model)
    @airports_ns.response(404, "Airport not found", error_model)
    @jwt_required()
    def get(self, iata):
        """Airlines operating at an airport."""
        current_account()
        airport = explore_airport_or_404(iata)
        page, page_size = page_arguments()

        airlines = explore_airport_airlines(airport.airport_id)
        rows = explore_page_slice(airlines, page, page_size)
        return paginated(
            [serialize_airline(airline) for airline in rows],
            page,
            page_size,
            len(airlines),
        )


@airports_ns.route("/<string:iata>/destinations")
class AirportDestinationsResource(Resource):
    """The airports reachable from this airport with a direct flight."""

    @airports_ns.doc(
        description=(
            "Return the distinct airports that can be reached from this airport "
            "with a direct (single-route) departure. This is the "
            "graph-navigation counterpart of `/routes?direction=departure`: it "
            "answers \"where can I fly to from here?\" with airport objects "
            "instead of route objects.\n\n"
            "Available to any active account."
        ),
        security=[JWT_SECURITY],
        params={**EXPLORE_PAGE_PARAMS},
    )
    @airports_ns.response(200, "A page of destination airports", airport_page_model)
    @airports_ns.response(400, "Invalid pagination parameter", error_model)
    @airports_ns.response(401, "Missing, invalid or expired token", error_model)
    @airports_ns.response(404, "Airport not found", error_model)
    @jwt_required()
    def get(self, iata):
        """Direct destinations of an airport."""
        current_account()
        airport = explore_airport_or_404(iata)
        page, page_size = page_arguments()

        destinations = explore_airport_destinations(airport.airport_id)
        rows = explore_page_slice(destinations, page, page_size)
        return paginated(
            [serialize_airport(destination) for destination in rows],
            page,
            page_size,
            len(destinations),
        )

@airlines_ns.route("")
class AirlineListResource(Resource):
    """Browse the airline catalogue with filtering, fuzzy search and paging."""

    @airlines_ns.doc(
        description=(
            "Return a paginated page of airlines. Available to **any active "
            "account** (admin or user).\n\n"
            "**Filters** (all combine with AND):\n"
            "* `q` - case-insensitive substring match over `name`, `country`, "
            "`iata_code` and `icao_code`.\n"
            "* `country` - exact match, case-insensitive.\n"
            "* `iata_code` - exact match, case-insensitive.\n\n"
            "**Fuzzy search**: add `fuzzy=true` to rank the `q` term against the "
            "airline `name` with RapidFuzz `WRatio` similarity (`Qntas` still "
            "finds `Qantas`). It requires a `q` value.\n\n"
            "Results are ordered by `airline_id`; fuzzy results are ordered by "
            "descending similarity."
        ),
        security=[JWT_SECURITY],
        params={
            **EXPLORE_PAGE_PARAMS,
            "q": {
                "in": "query",
                "type": "string",
                "description": "Free-text search term (case-insensitive substring).",
            },
            "country": {
                "in": "query",
                "type": "string",
                "description": "Exact country name, case-insensitive.",
            },
            "iata_code": {
                "in": "query",
                "type": "string",
                "description": "Exact IATA code, case-insensitive.",
            },
            "fuzzy": {
                "in": "query",
                "type": "boolean",
                "default": False,
                "description": "Rank the `q` matches by fuzzy name similarity.",
            },
        },
    )
    @airlines_ns.response(200, "A page of airlines", airline_page_model)
    @airlines_ns.response(400, "Invalid query parameter", error_model)
    @airlines_ns.response(401, "Missing, invalid or expired token", error_model)
    @jwt_required()
    def get(self):
        """List and search airlines."""
        current_account()
        page, page_size = page_arguments()

        query = Airline.query
        term = request.args.get("q", "").strip()
        country = (request.args.get("country") or "").strip()
        iata_code = (request.args.get("iata_code") or "").strip()
        fuzzy = explore_bool_arg("fuzzy")

        if country:
            query = query.filter(func.lower(Airline.country) == country.lower())
        if iata_code:
            query = query.filter(func.lower(Airline.iata_code) == iata_code.lower())

        if not term:
            if fuzzy:
                abort_json(400, "'fuzzy=true' requires a 'q' search term.")
            total = query.count()
            rows = (
                query.order_by(Airline.airline_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return paginated(
                [serialize_airline(airline) for airline in rows],
                page,
                page_size,
                total,
            )

        if fuzzy:
            ranked = explore_fuzzy_rank(
                query.order_by(Airline.airline_id).all(), term
            )
            rows = explore_page_slice(ranked, page, page_size)
            return paginated(
                [serialize_airline(airline) for airline in rows],
                page,
                page_size,
                len(ranked),
            )

        pattern = explore_like_pattern(term)
        query = query.filter(
            or_(
                Airline.name.ilike(pattern, escape="\\"),
                Airline.country.ilike(pattern, escape="\\"),
                Airline.iata_code.ilike(pattern, escape="\\"),
                Airline.icao_code.ilike(pattern, escape="\\"),
            )
        )
        total = query.count()
        rows = (
            query.order_by(Airline.airline_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return paginated(
            [serialize_airline(airline) for airline in rows], page, page_size, total
        )


@airlines_ns.route("/<string:iata>")
class AirlineResource(Resource):
    """Airline detail plus the statistics a client needs to navigate."""

    @airlines_ns.doc(
        description=(
            "Look up a single airline by IATA code (case-insensitive) and get "
            "`route_count` (routes it operates) plus `airport_count` (distinct "
            "airports it serves, counting both origins and destinations).\n\n"
            "The `_links` object points at the airline's `/routes` "
            "sub-resource. Available to any active account."
        ),
        security=[JWT_SECURITY],
    )
    @airlines_ns.response(200, "The airline", airline_detail_model)
    @airlines_ns.response(401, "Missing, invalid or expired token", error_model)
    @airlines_ns.response(404, "Airline not found", error_model)
    @jwt_required()
    def get(self, iata):
        """Airline detail with route statistics."""
        current_account()
        airline = explore_airline_or_404(iata)

        data = serialize_airline(airline)
        data["route_count"] = Route.query.filter(
            Route.airline_id == airline.airline_id
        ).count()
        data["airport_count"] = explore_airline_airport_count(airline.airline_id)
        return data


@airlines_ns.route("/<string:iata>/routes")
class AirlineRoutesResource(Resource):
    """All routes operated by one airline, filterable by endpoint."""

    @airlines_ns.doc(
        description=(
            "Return the routes operated by one airline, optionally narrowed to a "
            "specific origin and/or destination airport (IATA codes, "
            "case-insensitive).\n\n"
            "A well formed IATA code that is not present in the data simply "
            "yields an empty page; a malformed one is a 400. Routes are compact "
            "summaries - call `GET /api/routes/{route_id}` for the expanded "
            "representation. Available to any active account."
        ),
        security=[JWT_SECURITY],
        params={
            **EXPLORE_PAGE_PARAMS,
            "origin": {
                "in": "query",
                "type": "string",
                "description": "Only routes departing from this airport (3-letter IATA).",
            },
            "destination": {
                "in": "query",
                "type": "string",
                "description": "Only routes arriving at this airport (3-letter IATA).",
            },
        },
    )
    @airlines_ns.response(200, "A page of routes", route_page_model)
    @airlines_ns.response(400, "Invalid query parameter", error_model)
    @airlines_ns.response(401, "Missing, invalid or expired token", error_model)
    @airlines_ns.response(404, "Airline not found", error_model)
    @jwt_required()
    def get(self, iata):
        """Routes operated by an airline."""
        current_account()
        airline = explore_airline_or_404(iata)
        page, page_size = page_arguments()
        origin = explore_code_arg("origin", EXPLORE_AIRPORT_CODE_RE, "3-letter")
        destination = explore_code_arg(
            "destination", EXPLORE_AIRPORT_CODE_RE, "3-letter"
        )

        query = Route.query.filter(Route.airline_id == airline.airline_id)
        if origin:
            query = query.filter(func.lower(Route.origin_iata) == origin.lower())
        if destination:
            query = query.filter(
                func.lower(Route.destination_iata) == destination.lower()
            )

        total = query.count()
        rows = (
            query.order_by(Route.route_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return paginated(
            [serialize_route(route) for route in rows], page, page_size, total
        )

@routes_ns.route("")
class RouteListResource(Resource):
    """Search the route network by airline, endpoints and number of stops."""

    @routes_ns.doc(
        description=(
            "Return a paginated page of routes. Available to **any active "
            "account** (admin or user).\n\n"
            "**Filters** (all combine with AND):\n"
            "* `airline` - 2-letter airline IATA code;\n"
            "* `origin` / `destination` - 3-letter airport IATA codes;\n"
            "* `max_stops` - keep routes with `stops <= max_stops`;\n"
            "* `codeshare` - `Y` for codeshare routes, `N` for non-codeshare "
            "ones (the CSV leaves the column empty for non-codeshare routes, so "
            "`N` also matches `null`).\n\n"
            "A malformed code (wrong length) is a 400; a well formed code that "
            "does not exist yields an empty page with a 200, which lets clients "
            "distinguish a typo from an empty result set. Routes are compact "
            "summaries - call `GET /api/routes/{route_id}` for the expanded "
            "representation."
        ),
        security=[JWT_SECURITY],
        params={
            **EXPLORE_PAGE_PARAMS,
            "airline": {
                "in": "query",
                "type": "string",
                "description": "Airline IATA code (2 letters, case-insensitive).",
            },
            "origin": {
                "in": "query",
                "type": "string",
                "description": "Origin airport IATA code (3 letters, case-insensitive).",
            },
            "destination": {
                "in": "query",
                "type": "string",
                "description": "Destination airport IATA code (3 letters, case-insensitive).",
            },
            "max_stops": {
                "in": "query",
                "type": "integer",
                "minimum": 0,
                "description": "Maximum number of stops, inclusive.",
            },
            "codeshare": {
                "in": "query",
                "type": "string",
                "enum": ["Y", "N"],
                "description": "Y = codeshare only, N = non-codeshare only.",
            },
        },
    )
    @routes_ns.response(200, "A page of routes", route_page_model)
    @routes_ns.response(400, "Invalid query parameter", error_model)
    @routes_ns.response(401, "Missing, invalid or expired token", error_model)
    @jwt_required()
    def get(self):
        """List and filter routes."""
        current_account()
        page, page_size = page_arguments()
        airline = explore_code_arg("airline", EXPLORE_AIRLINE_CODE_RE, "2-letter")
        origin = explore_code_arg("origin", EXPLORE_AIRPORT_CODE_RE, "3-letter")
        destination = explore_code_arg(
            "destination", EXPLORE_AIRPORT_CODE_RE, "3-letter"
        )

        query = Route.query
        if airline:
            query = query.filter(func.lower(Route.airline_iata) == airline.lower())
        if origin:
            query = query.filter(func.lower(Route.origin_iata) == origin.lower())
        if destination:
            query = query.filter(
                func.lower(Route.destination_iata) == destination.lower()
            )

        raw_max_stops = request.args.get("max_stops")
        if raw_max_stops is not None and raw_max_stops.strip():
            try:
                max_stops = int(raw_max_stops)
            except (TypeError, ValueError):
                abort_json(
                    400,
                    "'max_stops' must be an integer greater than or equal to 0.",
                )
            if max_stops < 0:
                abort_json(
                    400,
                    "'max_stops' must be an integer greater than or equal to 0.",
                )
            query = query.filter(Route.stops <= max_stops)

        codeshare = (request.args.get("codeshare") or "").strip().upper()
        if codeshare:
            if codeshare not in ("Y", "N"):
                abort_json(400, "'codeshare' must be 'Y' or 'N'.")
            if codeshare == "Y":
                query = query.filter(func.upper(Route.codeshare) == "Y")
            else:
                # An empty CSV cell is stored as NULL and means "not a
                # codeshare", so `codeshare=N` must include the NULL rows.
                query = query.filter(
                    or_(
                        Route.codeshare.is_(None),
                        func.upper(Route.codeshare) == "N",
                    )
                )

        total = query.count()
        rows = (
            query.order_by(Route.route_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return paginated(
            [serialize_route(route) for route in rows], page, page_size, total
        )


@routes_ns.route("/<int:route_id>")
class RouteResource(Resource):
    """One route with its airline and both airports fully expanded."""

    @routes_ns.doc(
        description=(
            "Return a single route with the full airline object, the full origin "
            "airport object and the full destination airport object embedded "
            "under `airline`, `origin_airport` and `destination_airport`.\n\n"
            "This is the endpoint that lets a client navigate from a route to "
            "every related resource in one request, without knowing the SQLite "
            "schema or issuing follow-up calls. Available to any active account."
        ),
        security=[JWT_SECURITY],
    )
    @routes_ns.response(200, "The expanded route", route_expanded_model)
    @routes_ns.response(401, "Missing, invalid or expired token", error_model)
    @routes_ns.response(404, "Route not found", error_model)
    @jwt_required()
    def get(self, route_id):
        """Route detail with expanded airline and airports."""
        current_account()
        route = db.session.get(Route, route_id)
        if route is None:
            abort_json(404, f"Route {route_id} was not found.")
        return serialize_route(route, expand=True)

# ---------------------------------------------------------------------------
# Private travel plans
# ---------------------------------------------------------------------------
#
# A travel plan is a *private*, named collection of routes that belongs to
# exactly one account.  Every plan in this section is looked up through
# ``get_owned_plan()`` (defined in the shared core), which returns the plan only
# when it exists **and** belongs to the caller and aborts with 404 otherwise.
# Using 404 instead of 403 for "somebody else's plan" is deliberate: a 403
# would confirm that the plan id exists, which leaks information between
# accounts.  This rule applies to the admin account as well - an admin only ever
# sees the plans the admin account created itself.
#
# Routes are attached through the ``plan_routes`` association table, so a plan
# and a route can be linked many-to-many: several plans may contain the same
# route and the route dataset is never duplicated.  Adding a route is
# idempotent (the composite primary key already guarantees it at the database
# level), and deleting a plan only removes the association rows, never the
# routes themselves.

PLAN_SORTS = {
    "departure_date": (TravelPlan.departure_date.asc(), TravelPlan.plan_id.asc()),
    "-departure_date": (TravelPlan.departure_date.desc(), TravelPlan.plan_id.asc()),
    "name": (TravelPlan.name.asc(), TravelPlan.plan_id.asc()),
    "created_at": (TravelPlan.created_at.desc(), TravelPlan.plan_id.asc()),
}

plan_page_model = collection_model("PlanPage", plan_model)
plan_route_page_model = collection_model("PlanRoutePage", route_model)

plan_create_model = api.model(
    "PlanCreateRequest",
    {
        "name": fields.String(
            required=True,
            example="Japan Spring Trip",
            description="Plan name, 1-80 characters, unique per account.",
        ),
        "departure_date": fields.String(
            required=True,
            example="2027-04-01",
            description="Travel departure date in YYYY-MM-DD format.",
        ),
        "return_date": fields.String(
            required=True,
            example="2027-04-15",
            description="Travel return date in YYYY-MM-DD format, "
            "not earlier than departure_date.",
        ),
        "route_ids": fields.List(
            fields.Integer,
            example=[1, 2, 3],
            description="Optional ids of routes to add to the new plan.",
        ),
    },
)

plan_update_model = api.model(
    "PlanUpdateRequest",
    {
        "name": fields.String(example="Japan Spring Trip (revised)"),
        "departure_date": fields.String(example="2027-04-02"),
        "return_date": fields.String(example="2027-04-16"),
    },
)

plan_route_ids_model = api.model(
    "PlanRouteIdsRequest",
    {
        "route_ids": fields.List(
            fields.Integer,
            required=True,
            example=[1, 2],
            description="Route ids to add to the plan (existing ones are ignored).",
        )
    },
)

PLAN_PAGE_PARAMS = {
    "page": {
        "in": "query",
        "type": "integer",
        "default": 1,
        "minimum": 1,
        "description": "1-based page number.",
    },
    "page_size": {
        "in": "query",
        "type": "integer",
        "default": DEFAULT_PAGE_SIZE,
        "minimum": 1,
        "maximum": MAX_PAGE_SIZE,
        "description": f"Items per page (1-{MAX_PAGE_SIZE}).",
    },
}

def plans_bool_arg(name):
    """Read an optional boolean query flag such as ``expand``."""
    raw = request.args.get(name)
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in ("true", "1", "yes", "y"):
        return True
    if value in ("false", "0", "no", "n", ""):
        return False
    abort_json(400, f"'{name}' must be a boolean: true or false.")


def plans_invalid(field, issue):
    """Abort with 400 and a machine-readable ``details`` entry."""
    abort_json(
        400,
        "Request validation failed.",
        [{"field": field, "issue": issue}],
    )


def plans_validate_name(value):
    """Validate a plan name: a non-empty string of at most 80 characters."""
    if not isinstance(value, str) or not value.strip():
        plans_invalid("name", "must be a non-empty string of at most 80 characters")
    name = value.strip()
    if len(name) > 80:
        plans_invalid("name", "must be a non-empty string of at most 80 characters")
    return name


def plans_validate_range(departure_date, return_date):
    """Enforce ``return_date >= departure_date`` on the *final* pair of dates."""
    if return_date < departure_date:
        plans_invalid("return_date", "must not be earlier than departure_date")


def plans_route_ids(payload, required=False):
    """Validate a ``route_ids`` list and return the matching ``Route`` rows.

    Unknown ids abort with 404 and list *every* offending id in ``details``, so
    a client can fix its request in one round-trip instead of binary-searching
    the mistake.  Duplicate ids are collapsed silently (the association table
    would reject them anyway), which keeps the endpoint idempotent.
    """
    raw = payload.get("route_ids")
    if raw is None:
        if required:
            plans_invalid("route_ids", "is required")
        return []
    if not isinstance(raw, list):
        plans_invalid("route_ids", "must be a list of route ids")
    if required and not raw:
        plans_invalid("route_ids", "must contain at least one route id")

    route_ids = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            plans_invalid("route_ids", "must be a list of integers")
        if value not in route_ids:
            route_ids.append(value)
    if not route_ids:
        return []

    routes = Route.query.filter(Route.route_id.in_(route_ids)).all()
    found = {route.route_id: route for route in routes}
    missing = [route_id for route_id in route_ids if route_id not in found]
    if missing:
        abort_json(
            404,
            "Some route ids were not found: "
            + ", ".join(str(route_id) for route_id in missing)
            + ".",
            [
                {"field": "route_ids", "issue": f"route {route_id} does not exist"}
                for route_id in missing
            ],
        )
    return [found[route_id] for route_id in route_ids]


def plans_name_taken(owner_id, name, exclude_plan_id=None):
    """Return True when ``owner_id`` already has a plan called ``name``."""
    query = TravelPlan.query.filter(
        TravelPlan.owner_id == owner_id, TravelPlan.name == name
    )
    if exclude_plan_id is not None:
        query = query.filter(TravelPlan.plan_id != exclude_plan_id)
    return query.first() is not None


def plans_commit():
    """Commit the session, turning a name collision into a 409 instead of a 500."""
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort_json(
            409,
            "A travel plan with this name already exists for this account.",
        )

@plans_ns.route("")
class PlanListResource(Resource):
    """The authenticated account's own travel plans, plus plan creation."""

    @plans_ns.doc(
        description=(
            "Return a paginated page of the travel plans owned by the "
            "authenticated account. Plans owned by other accounts - including "
            "plans owned by other accounts while the caller is an admin - are "
            "never listed.\n\n"
            "**Sorting**: `departure_date` (default, earliest first), "
            "`-departure_date` (latest first), `name` (alphabetical) or "
            "`created_at` (newest first).\n\n"
            "**Expansion**: `expand=true` embeds the full route, airline and "
            "airport details of every plan. Without it a plan only reports "
            "`route_count` and links, which keeps the list payload small."
        ),
        security=[JWT_SECURITY],
        params={
            **PLAN_PAGE_PARAMS,
            "sort": {
                "in": "query",
                "type": "string",
                "enum": list(PLAN_SORTS.keys()),
                "default": "departure_date",
                "description": "Ordering of the returned plans.",
            },
            "expand": {
                "in": "query",
                "type": "boolean",
                "default": False,
                "description": "Embed the full route details of every plan.",
            },
        },
    )
    @plans_ns.response(200, "A page of travel plans", plan_page_model)
    @plans_ns.response(400, "Invalid sort or pagination parameter", error_model)
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @jwt_required()
    def get(self):
        """List my travel plans."""
        account = current_account()
        page, page_size = page_arguments()

        sort = request.args.get("sort", "departure_date")
        if sort not in PLAN_SORTS:
            abort_json(
                400,
                "'sort' must be one of: " + ", ".join(PLAN_SORTS.keys()) + ".",
            )
        expand = plans_bool_arg("expand")

        query = TravelPlan.query.filter(TravelPlan.owner_id == account.id)
        total = query.count()
        rows = (
            query.order_by(*PLAN_SORTS[sort])
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return paginated(
            [serialize_plan(plan, expand_routes=expand) for plan in rows],
            page,
            page_size,
            total,
        )

    @plans_ns.doc(
        description=(
            "Create a private travel plan owned by the authenticated account.\n\n"
            "* `name` is 1-80 characters and unique **per account**; two "
            "different accounts may use the same name, a duplicate for the same "
            "account is a 409.\n"
            "* `departure_date` and `return_date` use `YYYY-MM-DD`; the return "
            "date must not be earlier than the departure date (400 with a "
            "`details` entry otherwise).\n"
            "* `route_ids` is optional and attaches existing routes; unknown ids "
            "make the whole request fail with 404 *before* anything is written, "
            "so a plan is never created half-populated.\n\n"
            "The 201 response already embeds the route, airline and airport "
            "details of the new plan."
        ),
        security=[JWT_SECURITY],
    )
    @plans_ns.expect(plan_create_model)
    @plans_ns.response(201, "The created travel plan", plan_model)
    @plans_ns.response(400, "Request validation failed", error_model)
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "A referenced route does not exist", error_model)
    @plans_ns.response(409, "A plan with this name already exists", error_model)
    @jwt_required()
    def post(self):
        """Create a travel plan."""
        account = current_account()
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort_json(400, "Request body must be a JSON object.")

        name = plans_validate_name(payload.get("name"))
        if "departure_date" not in payload:
            plans_invalid("departure_date", "is required")
        if "return_date" not in payload:
            plans_invalid("return_date", "is required")
        departure_date = parse_date(payload["departure_date"], "departure_date")
        return_date = parse_date(payload["return_date"], "return_date")
        plans_validate_range(departure_date, return_date)
        routes = plans_route_ids(payload)

        if plans_name_taken(account.id, name):
            abort_json(
                409, f"You already have a travel plan named '{name}'."
            )

        plan = TravelPlan(
            name=name,
            departure_date=departure_date,
            return_date=return_date,
            owner_id=account.id,
        )
        plan.routes = routes
        db.session.add(plan)
        plans_commit()
        # 201 + Location is the standard "created" answer: the client learns
        # both the new resource body and the URL it now lives at.
        return (
            serialize_plan(plan, expand_routes=True),
            201,
            {"Location": f"/api/plans/{plan.plan_id}"},
        )

@plans_ns.route("/<int:plan_id>")
class PlanResource(Resource):
    """One private travel plan: detail, update and removal."""

    @plans_ns.doc(
        description=(
            "Return one plan owned by the authenticated account, including the "
            "full details of every route it contains (route, airline, origin "
            "airport and destination airport).\n\n"
            "A plan that does not exist and a plan owned by another account "
            "both produce the same 404, so the API never leaks the existence of "
            "other accounts' plans."
        ),
        security=[JWT_SECURITY],
    )
    @plans_ns.response(200, "The travel plan with its routes", plan_model)
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "Plan not found for this account", error_model)
    @jwt_required()
    def get(self, plan_id):
        """Travel plan detail."""
        plan = get_owned_plan(plan_id)
        return serialize_plan(plan, expand_routes=True)

    @plans_ns.doc(
        description=(
            "Update only the fields that are present in the request body: "
            "`name`, `departure_date` and/or `return_date`. Fields that are "
            "omitted keep their current value; unknown fields and an empty body "
            "are rejected with 400.\n\n"
            "The date range is re-validated against the *resulting* pair, so "
            "moving only the departure date past an unchanged return date is "
            "caught. Renaming to a name that another plan of the same account "
            "already uses is a 409."
        ),
        security=[JWT_SECURITY],
    )
    @plans_ns.expect(plan_update_model)
    @plans_ns.response(200, "The updated travel plan", plan_model)
    @plans_ns.response(400, "Request validation failed", error_model)
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "Plan not found for this account", error_model)
    @plans_ns.response(409, "A plan with this name already exists", error_model)
    @jwt_required()
    def patch(self, plan_id):
        """Update a travel plan."""
        plan = get_owned_plan(plan_id)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort_json(400, "Request body must be a JSON object.")

        allowed = {"name", "departure_date", "return_date"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            plans_invalid(
                unknown[0],
                "is not updatable; PATCH accepts name, departure_date "
                "and return_date",
            )
        if not payload:
            abort_json(
                400,
                "Provide at least one of: name, departure_date, return_date.",
            )

        new_name = plan.name
        new_departure_date = plan.departure_date
        new_return_date = plan.return_date

        if "name" in payload:
            new_name = plans_validate_name(payload["name"])
            if new_name != plan.name and plans_name_taken(
                plan.owner_id, new_name, exclude_plan_id=plan.plan_id
            ):
                abort_json(
                    409, f"You already have a travel plan named '{new_name}'."
                )
        if "departure_date" in payload:
            new_departure_date = parse_date(
                payload["departure_date"], "departure_date"
            )
        if "return_date" in payload:
            new_return_date = parse_date(payload["return_date"], "return_date")

        # Re-validate the pair after merging old and new values: changing one
        # date can turn a previously valid range into an invalid one.
        plans_validate_range(new_departure_date, new_return_date)

        plan.name = new_name
        plan.departure_date = new_departure_date
        plan.return_date = new_return_date
        plans_commit()
        return serialize_plan(plan, expand_routes=True)

    @plans_ns.doc(
        description=(
            "Delete one of the authenticated account's plans. The `plan_routes` "
            "association rows are removed first and the routes themselves are "
            "left untouched, because a route may still belong to other plans. "
            "Responds with 204 and no body."
        ),
        security=[JWT_SECURITY],
    )
    @plans_ns.response(204, "The plan was deleted")
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "Plan not found for this account", error_model)
    @jwt_required()
    def delete(self, plan_id):
        """Delete a travel plan."""
        plan = get_owned_plan(plan_id)
        plan.routes.clear()
        db.session.delete(plan)
        db.session.commit()
        return "", 204

@plans_ns.route("/<int:plan_id>/routes")
class PlanRoutesResource(Resource):
    """The routes of one plan: list them or add more (idempotently)."""

    @plans_ns.doc(
        description=(
            "Return the plan's routes as a paginated collection.\n\n"
            "* Without `expand` each item is a compact route summary (IATA codes "
            "plus `_links` to the airline and both airports).\n"
            "* With `expand=true` every route embeds the full airline, origin "
            "airport and destination airport objects, so one call is enough to "
            "render the whole plan.\n\n"
            "The plan must be owned by the authenticated account."
        ),
        security=[JWT_SECURITY],
        params={
            **PLAN_PAGE_PARAMS,
            "expand": {
                "in": "query",
                "type": "boolean",
                "default": False,
                "description": "Embed the airline and airport objects of every route.",
            },
        },
    )
    @plans_ns.response(200, "A page of routes", plan_route_page_model)
    @plans_ns.response(400, "Invalid pagination parameter", error_model)
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "Plan not found for this account", error_model)
    @jwt_required()
    def get(self, plan_id):
        """List the routes of a travel plan."""
        plan = get_owned_plan(plan_id)
        page, page_size = page_arguments()
        expand = plans_bool_arg("expand")

        routes = sorted(plan.routes, key=lambda route: route.route_id)
        rows = routes[(page - 1) * page_size : page * page_size]
        return paginated(
            [serialize_route(route, expand=expand) for route in rows],
            page,
            page_size,
            len(routes),
        )

    @plans_ns.doc(
        description=(
            "Attach one or more existing routes to the plan.\n\n"
            "The operation is **idempotent**: route ids that are already part of "
            "the plan are ignored instead of raising a duplicate-key error, so "
            "retrying the same request is safe. Unknown route ids abort the "
            "whole request with 404 and are listed in `details`, which leaves "
            "the plan untouched. The 200 response is the updated plan with its "
            "full route details."
        ),
        security=[JWT_SECURITY],
    )
    @plans_ns.expect(plan_route_ids_model)
    @plans_ns.response(200, "The updated travel plan", plan_model)
    @plans_ns.response(400, "Invalid route_ids payload", error_model)
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "Plan or route not found", error_model)
    @jwt_required()
    def post(self, plan_id):
        """Add routes to a travel plan."""
        plan = get_owned_plan(plan_id)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort_json(400, "Request body must be a JSON object.")

        routes = plans_route_ids(payload, required=True)
        already_there = {route.route_id for route in plan.routes}
        for route in routes:
            if route.route_id not in already_there:
                plan.routes.append(route)
                already_there.add(route.route_id)
        plans_commit()
        return serialize_plan(plan, expand_routes=True)


@plans_ns.route("/<int:plan_id>/routes/<int:route_id>")
class PlanRouteResource(Resource):
    """Remove a single route from one plan."""

    @plans_ns.doc(
        description=(
            "Detach one route from the plan. Only the association row is "
            "deleted - the route itself stays in the catalogue. A route that is "
            "not part of the plan produces 404, just like a plan that is not "
            "owned by the caller. Responds with 204 and no body."
        ),
        security=[JWT_SECURITY],
    )
    @plans_ns.response(204, "The route was removed from the plan")
    @plans_ns.response(401, "Missing, invalid or expired token", error_model)
    @plans_ns.response(403, "The account has been deactivated", error_model)
    @plans_ns.response(404, "Plan not found or route not part of the plan",
                       error_model)
    @jwt_required()
    def delete(self, plan_id, route_id):
        """Remove a route from a travel plan."""
        plan = get_owned_plan(plan_id)
        route = next(
            (item for item in plan.routes if item.route_id == route_id), None
        )
        if route is None:
            abort_json(
                404,
                f"Route {route_id} is not part of travel plan {plan_id}.",
            )
        plan.routes.remove(route)
        db.session.commit()
        return "", 204


# ---------------------------------------------------------------------------
# Exporting the caller's own travel plans
#
# GET /api/plans/export renders the authenticated account's plans either as a
# self-contained JSON attachment (``format=json``, the default) or as an inline
# PNG Gantt timeline of up to five future plans (``format=image``).
#
# matplotlib is imported *inside* the render helper on purpose: it is only
# needed when an image is requested, and pyplot must be imported after the
# headless "Agg" backend has been selected.
# ---------------------------------------------------------------------------

EXPORT_FORMAT_JSON = "json"
EXPORT_FORMAT_IMAGE = "image"
EXPORT_ALLOWED_FORMATS = (EXPORT_FORMAT_JSON, EXPORT_FORMAT_IMAGE)
EXPORT_MAX_IMAGE_PLANS = 5
EXPORT_IMAGE_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd")
# DejaVu Sans ships with matplotlib but has no CJK glyphs. matplotlib >= 3.6
# walks this stack glyph by glyph, so a Chinese plan name still renders when a
# CJK font is installed (PingFang on macOS, Noto/WenQuanYi on Linux, YaHei on
# Windows). Without any CJK font the label degrades to boxed glyphs but the
# downloaded JSON still keeps the original name.
EXPORT_FONT_STACK = (
    "DejaVu Sans",
    "PingFang SC",
    "Hiragino Sans GB",
    "Heiti SC",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
    "Microsoft YaHei",
    "SimHei",
)

plan_export_model = api.model(
    "TravelPlanExport",
    {
        "account": fields.String(
            description="Username that owns the exported plans", example="user"
        ),
        "exported_at": fields.String(
            description="UTC timestamp of the export, ISO-8601 with a trailing Z",
            example="2026-10-26T02:30:00Z",
        ),
        "plan_count": fields.Integer(
            description="Number of plans contained in `plans`", example=2
        ),
        "plans": fields.List(
            fields.Nested(plan_model),
            description="Every plan of the account, ordered by `departure_date` "
            "ascending. Each plan embeds its routes, and every route embeds the "
            "full airline and airport objects.",
        ),
    },
)

EXPORT_DESCRIPTION = """
Export the travel plans that belong to the **authenticated account**. Plans are
private: every account (the `admin` account included) can only export its own
plans, and another account's plans are never part of the response.

### Content negotiation

| priority | how the representation is chosen |
|---|---|
| 1 | `?format=json` or `?format=image` - an explicit query parameter always wins |
| 2 | `Accept: image/png` (any q-value) selects the PNG image |
| 3 | anything else, including `*/*` - the JSON document is returned |

So `curl` without extra headers gets JSON, a browser that asks for `image/png`
gets the picture, and `?format=...` is the deterministic choice for scripts.

### `format=json` (default) - downloadable document

* `Content-Type: application/json`
* `Content-Disposition: attachment; filename="travel_plans_<username>.json"`,
  so browsers save the response as a file instead of rendering it.
* The body is **self-contained** and can be consumed offline:

| field | meaning |
|---|---|
| `account` | username that owns the plans |
| `exported_at` | UTC timestamp of the export (`...Z`) |
| `plan_count` | number of plans in `plans` |
| `plans` | all plans ordered by `departure_date` ascending |

* Every plan object embeds a `routes` array. Each route contains the complete
  `airline`, `origin_airport` and `destination_airport` objects, not only their
  identifiers, so no follow-up request is needed to know what the plan covers.
* An account without plans still receives `200` with `"plan_count": 0` and an
  empty `plans` array.

### `format=image` - inline PNG timeline

* `Content-Type: image/png`, rendered inline (not an attachment) so the browser
  displays it directly. The figure is produced with the headless `Agg` backend.
* Shows at most **five** plans whose `departure_date` is later than the current
  (server local) date, ordered by nearest departure first - a Gantt-style
  timeline: one row per plan, a bar from departure to return, annotated with
  the plan name and its route count.
* If the account has no future plan, the response is `404` with the usual JSON
  error envelope: `{"code": 404, "message": "You have no upcoming travel plans
  to visualise."}` (a JSON body even though an image was requested).

### Errors

| status | meaning |
|---|---|
| 400 | `format` is present but neither `json` nor `image` |
| 401 | missing, invalid or expired bearer token |
| 403 | the account is deactivated |
| 404 | no future plans for `format=image` |
"""

def export_requested_format() -> str:
    """Resolve the requested representation using the documented precedence."""
    requested = (request.args.get("format") or "").strip().lower()
    if requested:
        if requested not in EXPORT_ALLOWED_FORMATS:
            abort_json(
                400,
                f"Unsupported export format '{requested}'. Use 'json' or 'image'.",
            )
        return requested
    # An explicit Accept: image/png opts into the picture; everything else
    # (curl's "*/*", a browser's text/html preference, application/json) keeps
    # the JSON document so downloads keep working without extra parameters.
    accept_header = (request.headers.get("Accept") or "").lower()
    if "image/png" in accept_header:
        return EXPORT_FORMAT_IMAGE
    return EXPORT_FORMAT_JSON


def export_owned_plans(account: Account):
    """All plans of ``account`` ordered by departure date, earliest first."""
    return (
        TravelPlan.query.filter(TravelPlan.owner_id == account.id)
        .order_by(TravelPlan.departure_date.asc(), TravelPlan.plan_id.asc())
        .all()
    )


def export_future_plans(account: Account):
    """Up to five upcoming plans, nearest departure first."""
    today = date.today()
    return (
        TravelPlan.query.filter(
            TravelPlan.owner_id == account.id,
            TravelPlan.departure_date > today,
        )
        .order_by(TravelPlan.departure_date.asc(), TravelPlan.plan_id.asc())
        .limit(EXPORT_MAX_IMAGE_PLANS)
        .all()
    )


def export_safe_filename(account: Account, extension: str) -> str:
    """Build a header-safe file name, e.g. ``travel_plans_user.json``."""
    safe_username = re.sub(r"[^A-Za-z0-9_.-]", "_", account.username) or "account"
    return f"travel_plans_{safe_username}.{extension}"


def export_json_payload(account: Account, plans) -> dict:
    """Build the self-contained JSON document returned by ``format=json``."""
    return {
        "account": account.username,
        "exported_at": iso_utc(utcnow()),
        "plan_count": len(plans),
        "plans": [serialize_plan(plan, expand_routes=True) for plan in plans],
    }


def export_json_response(account: Account):
    """Return the JSON document as a downloadable attachment."""
    plans = export_owned_plans(account)
    body = json.dumps(
        export_json_payload(account, plans), indent=2, ensure_ascii=False
    )
    response = make_response(body, 200)
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{export_safe_filename(account, "json")}"'
    )
    response.headers["Cache-Control"] = "no-store"
    return response
def export_display_width(text: str) -> int:
    """Approximate the display width of ``text`` (CJK glyphs count as two)."""
    return sum(2 if ord(character) > 0x2E80 else 1 for character in text)


def export_shorten_label(text: str, max_width: int = 30) -> str:
    """Truncate a label by display width, appending ``...`` when it is cut."""
    if export_display_width(text) <= max_width:
        return text
    kept, width = [], 0
    for character in text:
        character_width = 2 if ord(character) > 0x2E80 else 1
        if width + character_width > max_width - 3:
            break
        kept.append(character)
        width += character_width
    return "".join(kept).rstrip() + "..."


def export_route_count_label(count: int) -> str:
    """Human friendly ``1 route`` / ``3 routes`` label."""
    return f"{count} route" if count == 1 else f"{count} routes"


def export_render_timeline_png(account: Account, plans) -> io.BytesIO:
    """Draw a Gantt-style timeline of ``plans`` and return it as a PNG buffer.

    matplotlib is imported lazily here so that importing the application never
    pulls in the plotting stack, and the headless ``Agg`` backend is forced
    before ``pyplot`` is imported (a server has no display).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    # Only advertise font families that are actually installed: matplotlib
    # falls back glyph by glyph across this list, and unknown family names would
    # only spam the log with "font family not found" messages.
    installed_families = {font.name for font in font_manager.fontManager.ttflist}
    font_stack = [
        family for family in EXPORT_FONT_STACK if family in installed_families
    ]
    plt.rcParams["font.family"] = font_stack or ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    today = date.today()
    today_number = mdates.date2num(datetime.combine(today, datetime.min.time()))
    row_count = len(plans)

    figure = plt.figure(figsize=(11.5, max(3.0, 1.1 + 0.95 * row_count)), dpi=150)
    try:
        axes = figure.add_subplot(1, 1, 1)
        axes.set_axisbelow(True)

        positions, starts, ends = [], [], []
        for index, plan in enumerate(plans):
            departure = datetime.combine(plan.departure_date, datetime.min.time())
            return_day = datetime.combine(plan.return_date, datetime.min.time())
            start_number = mdates.date2num(departure)
            # +1 day: a trip that leaves and returns on the same day still gets
            # a visible bar instead of a zero-width sliver.
            end_number = mdates.date2num(return_day) + 1.0
            starts.append(start_number)
            ends.append(end_number)
            positions.append(index)

            color = EXPORT_IMAGE_COLORS[index % len(EXPORT_IMAGE_COLORS)]
            axes.barh(
                index,
                max(end_number - start_number, 1.0),
                left=start_number,
                height=0.55,
                color=color,
                edgecolor="white",
                linewidth=1.0,
                zorder=3,
            )
            axes.text(
                end_number,
                index,
                "  " + export_route_count_label(len(plan.routes)),
                va="center",
                ha="left",
                fontsize=9,
                color="#333333",
                zorder=4,
            )

        axes.set_yticks(positions)
        axes.set_yticklabels(
            [
                export_shorten_label(plan.name or f"Plan {plan.plan_id}")
                for plan in plans
            ],
            fontsize=10,
        )
        axes.invert_yaxis()
        # Pad the y axis explicitly: with a single plan the auto-scaled limits
        # would make the bar fill the whole axes and look like a bar chart
        # instead of one row of a Gantt timeline.
        axes.set_ylim(row_count - 0.4, -0.6)
        axes.tick_params(axis="y", length=0)

        axes.axvline(
            today_number, color="#999999", linestyle="--", linewidth=1.0, zorder=2
        )
        axes.annotate(
            "today",
            xy=(today_number, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(4, -10),
            textcoords="offset points",
            fontsize=8,
            color="#666666",
            ha="left",
            va="top",
        )

        low = min(starts + [today_number])
        high = max(ends)
        span = max(high - low, 1.0)
        left_pad = max(span * 0.03, 0.5)
        right_pad = max(span * 0.10, 2.0)  # room for the route-count labels
        axes.set_xlim(low - left_pad, high + right_pad)

        axes.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
        axes.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
        for tick_label in axes.get_xticklabels():
            tick_label.set_rotation(25)
            tick_label.set_ha("right")

        axes.grid(axis="x", color="#e2e2e2", linestyle=":", linewidth=0.9)
        for side in ("top", "right", "left"):
            axes.spines[side].set_visible(False)

        axes.set_title(
            f"Upcoming travel plans for {account.username}",
            loc="left",
            fontsize=14,
            fontweight="bold",
            pad=24,
        )
        axes.text(
            0.0,
            1.015,
            "Up to 5 future plans, nearest departure first"
            f"  |  generated {iso_utc(utcnow())}",
            transform=axes.transAxes,
            fontsize=9,
            color="#666666",
            va="bottom",
        )

        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    finally:
        # Always release the figure; a leaked figure would accumulate memory in
        # a long running server process.
        plt.close(figure)

    buffer.seek(0)
    return buffer

def export_image_response(account: Account):
    """Return the PNG timeline, or a JSON 404 when nothing is upcoming."""
    future_plans = export_future_plans(account)
    if not future_plans:
        abort_json(404, "You have no upcoming travel plans to visualise.")
    buffer = export_render_timeline_png(account, future_plans)
    response = send_file(
        buffer,
        mimetype="image/png",
        as_attachment=False,
        download_name=export_safe_filename(account, "png"),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@plans_ns.route("/export")
class PlanExportResource(Resource):
    """Export the authenticated account's own travel plans as JSON or PNG."""

    @plans_ns.doc(
        summary="Export my travel plans (JSON attachment or PNG timeline)",
        description=EXPORT_DESCRIPTION,
        security=JWT_SECURITY,
    )
    @plans_ns.param(
        "format",
        "Output representation: `json` (downloadable document, default) or "
        "`image` (inline PNG timeline of up to five future plans). When the "
        "parameter is omitted the `Accept` header is consulted: `image/png` "
        "selects the image, anything else selects JSON.",
        _in="query",
        enum=[EXPORT_FORMAT_JSON, EXPORT_FORMAT_IMAGE],
        required=False,
    )
    @plans_ns.response(404, "No upcoming plans for `format=image`.", error_model)
    @plans_ns.response(400, "Unsupported `format` value.", error_model)
    @plans_ns.response(401, "Missing, invalid or expired bearer token.", error_model)
    @plans_ns.response(403, "The account has been deactivated.", error_model)
    @plans_ns.response(
        200,
        "The JSON export document (default / `format=json`). When `format=image` "
        "is requested the same status returns an `image/png` timeline instead.",
        plan_export_model,
    )
    @plans_ns.response(
        200, "PNG timeline image when `format=image` (`Content-Type: image/png`)."
    )
    @plans_ns.produces(["application/json", "image/png"])
    @jwt_required()
    def get(self):
        """Export the caller's own plans as a JSON attachment or a PNG."""
        account = current_account()
        if export_requested_format() == EXPORT_FORMAT_IMAGE:
            return export_image_response(account)
        return export_json_response(account)

# `format=image` 只有在账号至少有一个未来计划时才渲染时间线；
# 没有未来计划时返回标准的 404 JSON 错误信封
# （"You have no upcoming travel plans to visualise."）。

# ---------------------------------------------------------------
# 前端托管：`airtrip-web/dist` 挂在 /app，/docs 是 Swagger，
# 其余非 /api 路径回落到 index.html（SPA history 路由需要）。
# ---------------------------------------------------------------
FRONTEND_DIR = os.path.join(BASE_DIR, "airtrip-web", "dist")
FRONTEND_INDEX = os.path.join(FRONTEND_DIR, "index.html")


@app.route("/")
def frontend_root():
    """Send the site root to the web client."""
    return redirect("/app/")


@app.route("/app/", defaults={"asset_path": ""})
@app.route("/app/<path:asset_path>")
def frontend(asset_path: str):
    """Serve the built SPA, falling back to index.html for client routes."""
    if asset_path:
        candidate = os.path.abspath(os.path.join(FRONTEND_DIR, asset_path))
        root = os.path.abspath(FRONTEND_DIR)
        if os.path.isfile(candidate) and candidate.startswith(root + os.sep):
            return send_from_directory(FRONTEND_DIR, asset_path)
    if os.path.isfile(FRONTEND_INDEX):
        return send_file(FRONTEND_INDEX)
    return (
        jsonify(
            {
                "code": 503,
                "message": "Frontend bundle is missing. Run `npm run build` "
                "in airtrip-web first.",
            }
        ),
        503,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

