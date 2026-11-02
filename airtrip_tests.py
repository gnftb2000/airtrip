"""AirTrip API - REST client test suite.

This suite treats the API as a black box: it talks to it over HTTP with
``requests`` and never imports the application, so it tests exactly what a
client sees.

How to run
----------
1. Start the API in one terminal.  Use a **fresh database**: delete
   ``airtrip.db`` before starting so the two built-in accounts are seeded and
   the CSV import starts from an empty state::

       rm -f airtrip.db
       python airtrip_api.py

2. Run the tests from the directory that contains the three CSV files
   (``airlines.csv``, ``airports.csv``, ``routes.csv``).  The import tests
   upload them by their **relative path**::

       pytest airtrip_tests.py -v

The base URL defaults to ``http://127.0.0.1:5000`` and can be overridden with
the ``API_BASE_URL`` environment variable, which is handy when the API runs on a
different port.

Conventions
-----------
* Every test docstring states what the test proves.
* Every test asserts three things: the **HTTP status code**, the **JSON
  structure / data correctness**, and the **error message** for invalid or
  unauthorised requests.
* The tests do not depend on their execution order.  They use the two seeded
  accounts only for the scenarios that require them and create disposable
  accounts (with a random ``uuid4`` suffix) for everything else; those accounts
  and their plans are deleted again in fixture teardown.  The suite can therefore
  be re-run against the same database without leaving data behind.
"""

import io
import os
import struct
import uuid
from datetime import date, timedelta

import pytest
import requests

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
BASE = f"{BASE_URL}/api"
TIMEOUT = 20  # seconds

ADMIN_CREDENTIALS = ("admin", "admin")
USER_CREDENTIALS = ("user", "user")

#: Dataset key -> CSV file name.  The files are read from the working directory.
CSV_FILES = {
    "airlines": "airlines.csv",
    "airports": "airports.csv",
    "routes": "routes.csv",
}

#: Row counts of the three CSV files shipped with the project.
DATASET_COUNTS = {"airlines": 15, "airports": 46, "routes": 260}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def url(path):
    """Build an absolute URL for an API path such as ``/airports``."""
    return f"{BASE}{path}"


def auth(token):
    """Return the ``Authorization`` header for a JWT access token."""
    return {"Authorization": f"Bearer {token}"}


def call(method, path, token=None, **kwargs):
    """Send one request to the API, aborting the run when the server is down."""
    headers = dict(kwargs.pop("headers", {}) or {})
    if token is not None:
        headers.update(auth(token))
    try:
        response = requests.request(
            method, url(path), headers=headers, timeout=TIMEOUT, **kwargs
        )
    except requests.ConnectionError:
        pytest.exit(
            f"The API is not reachable at {BASE_URL}. Start airtrip_api.py first.",
            returncode=2,
        )
    return response


def expect(response, status, label):
    """Assert the HTTP status code of ``response`` and return it."""
    assert response.status_code == status, (
        f"{label}: expected HTTP {status}, got {response.status_code} - "
        f"{response.text[:400]}"
    )
    return response


def expect_error(response, status, label, message_contains=None):
    """Assert the status code and the standard error envelope; return the body."""
    expect(response, status, label)
    body = response.json()
    assert isinstance(body, dict), f"{label}: error body must be a JSON object"
    assert body.get("code") == status, (
        f"{label}: expected body code {status}, got {body.get('code')}"
    )
    message = body.get("message")
    assert isinstance(message, str) and message, f"{label}: error needs a message"
    if message_contains is not None:
        assert message_contains.lower() in message.lower(), (
            f"{label}: message {message!r} does not contain "
            f"{message_contains!r}"
        )
    return body


def login(username, password):
    """Log in and return the access token, failing fast if the login breaks."""
    response = call(
        "POST", "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, (
        f"login as {username!r} failed: {response.status_code} {response.text[:400]}\n"
        "Is the API running against a fresh database?"
    )
    return response.json()["access_token"]


def unique_username(prefix="tmp_user"):
    """Return a username that is unique to this test run."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------


def import_files(token, *dataset_keys):
    """Upload the named CSV files (from the working directory) in one request."""
    opened = []
    files = {}
    try:
        for key in dataset_keys:
            file_name = CSV_FILES[key]
            assert os.path.exists(file_name), (
                f"{file_name!r} must be in the working directory ({os.getcwd()}); "
                "the import tests upload the project CSV files by relative path"
            )
            handle = open(file_name, "rb")
            opened.append(handle)
            files[key] = (file_name, handle, "text/csv")
        return call("POST", "/import", token=token, files=files)
    finally:
        for handle in opened:
            handle.close()


def import_csv_text(token, dataset_key, file_name, text):
    """Upload a synthetic CSV document (used for the invalid-file tests)."""
    return call(
        "POST",
        "/import",
        token=token,
        files={dataset_key: (file_name, io.BytesIO(text.encode("utf-8")), "text/csv")},
    )


def read_csv_rows(file_name):
    """Return the header and the data rows of a CSV file from the cwd."""
    with open(file_name, encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip()]
    return lines[0], lines[1:]


def dataset_counts(token):
    """Return ``{dataset: row_count}`` as currently stored in the database."""
    response = call("GET", "/import/status", token=token)
    if response.status_code == 200:
        body = response.json()
        counts = body.get("counts") if isinstance(body.get("counts"), dict) else body
        return {name: counts.get(name) for name in CSV_FILES}
    # /import/status reports the loaded datasets; when the database was populated
    # some other way (for example a fixture that seeded it directly) the counts
    # can still be read from the public collection endpoints.
    counts = {}
    for name, path in (
        ("airlines", "/airlines"),
        ("airports", "/airports"),
        ("routes", "/routes"),
    ):
        page = call("GET", path, token=token, params={"page_size": 1})
        counts[name] = page.json().get("total") if page.status_code == 200 else None
    return counts

# ---------------------------------------------------------------------------
# Plan helpers
# ---------------------------------------------------------------------------


def create_plan(token, name, departure_offset, duration, route_ids=None):
    """POST a plan whose dates are ``departure_offset`` days from today."""
    departure = date.today() + timedelta(days=departure_offset)
    payload = {
        "name": name,
        "departure_date": departure.isoformat(),
        "return_date": (departure + timedelta(days=duration)).isoformat(),
    }
    if route_ids:
        payload["route_ids"] = list(route_ids)
    return call("POST", "/plans", token=token, json=payload)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def admin_token():
    """Session-wide token of the seeded administrator account."""
    return login(*ADMIN_CREDENTIALS)


@pytest.fixture(scope="session")
def user_token():
    """Session-wide token of the seeded normal user account."""
    return login(*USER_CREDENTIALS)


@pytest.fixture(scope="session")
def dataset(admin_token):
    """Make sure the three CSV datasets are loaded; return counts.

    On a freshly created database the datasets are imported here, before any
    test creates travel plans (so replacing the route dataset can never collide
    with a plan).  When the database already contains the expected rows the
    import is skipped, which keeps the suite fast on re-runs.
    """
    counts = dataset_counts(admin_token)
    if counts != DATASET_COUNTS:
        response = import_files(admin_token, "airlines", "airports", "routes")
        expect(response, 200, "bootstrap import of the three CSV datasets")
        counts = dataset_counts(admin_token)
    assert counts == DATASET_COUNTS, (
        f"the imported dataset has unexpected row counts: {counts} != "
        f"{DATASET_COUNTS}"
    )
    return counts


@pytest.fixture(scope="session")
def sample_routes(dataset, user_token):
    """A few routes from the imported dataset, used to build travel plans."""
    response = call("GET", "/routes", token=user_token, params={"page_size": 5})
    expect(response, 200, "read sample routes")
    items = response.json()["items"]
    assert len(items) >= 3, "the dataset must contain at least three routes"
    return items


@pytest.fixture()
def temp_user(admin_token):
    """Create a disposable user account and delete it (and its plans) afterwards."""
    username = unique_username()
    password = "T3st-pass"
    response = call(
        "POST",
        "/users",
        token=admin_token,
        json={"username": username, "password": password},
    )
    expect(response, 201, f"create disposable user {username}")
    account = response.json()
    token = login(username, password)
    yield {
        "username": username,
        "password": password,
        "id": account["id"],
        "token": token,
    }
    # A test may have deactivated the account; reactivate it before deleting.
    call("PATCH", f"/users/{username}", token=admin_token, json={"is_active": True})
    call("DELETE", f"/users/{username}", token=admin_token)

# ---------------------------------------------------------------------------
# User management and access control
# ---------------------------------------------------------------------------


def test_req1_login_success():
    """Valid credentials return a JWT bearer token and the account.

    Also proves that the token response never contains password material.
    """
    response = call(
        "POST", "/auth/login", json={"username": "admin", "password": "admin"}
    )
    expect(response, 200, "admin login")
    body = response.json()
    assert isinstance(body.get("access_token"), str) and body["access_token"]
    assert body.get("token_type") == "Bearer"
    assert isinstance(body.get("expires_in"), int) and body["expires_in"] > 0
    account = body.get("account") or {}
    assert account.get("username") == "admin"
    assert account.get("role") == "admin"
    assert account.get("is_active") is True
    assert "password" not in str(account).lower()


def test_req1_login_wrong_password():
    """A wrong password returns 401 with the standard error envelope."""
    response = call(
        "POST", "/auth/login", json={"username": "admin", "password": "wrong-pass"}
    )
    body = expect_error(
        response, 401, "login with a wrong password", "invalid username or password"
    )
    assert set(body) >= {"code", "message"}


def test_req1_missing_or_invalid_token_rejected():
    """Protected endpoints reject missing and malformed tokens with 401."""
    expect_error(call("GET", "/auth/me"), 401, "request without a token")
    expect_error(
        call("GET", "/auth/me", token="this-is-not-a-jwt"),
        401,
        "request with a malformed token",
    )


def test_req1_auth_me_returns_current_account(user_token):
    """/auth/me returns the account behind the token, without secrets."""
    response = call("GET", "/auth/me", token=user_token)
    expect(response, 200, "GET /auth/me")
    account = response.json()
    assert account.get("username") == "user"
    assert account.get("role") == "user"
    assert account.get("is_active") is True
    assert "password_hash" not in account


def test_req1_admin_creates_user_account(admin_token):
    """The admin creates a user account (201) that can immediately log in."""
    username = unique_username("created")
    password = "Cr3ated-pass"
    try:
        response = call(
            "POST",
            "/users",
            token=admin_token,
            json={"username": username, "password": password},
        )
        expect(response, 201, "create user account")
        account = response.json()
        assert account.get("username") == username
        assert account.get("role") == "user"
        assert account.get("is_active") is True
        assert "password_hash" not in account
        assert login(username, password)  # the new account can authenticate
    finally:
        call("DELETE", f"/users/{username}", token=admin_token)


def test_req1_duplicate_username_conflict(admin_token):
    """Creating an existing username is a 409 conflict."""
    username = unique_username("dup")
    payload = {"username": username, "password": "Cr3ated-pass"}
    try:
        expect(
            call("POST", "/users", token=admin_token, json=payload),
            201,
            "first create",
        )
        expect_error(
            call("POST", "/users", token=admin_token, json=payload),
            409,
            "duplicate username",
            "already exists",
        )
    finally:
        call("DELETE", f"/users/{username}", token=admin_token)


def test_req1_invalid_username_rejected(admin_token):
    """Usernames outside the documented format are a 400, not a 500."""
    expect_error(
        call(
            "POST",
            "/users",
            token=admin_token,
            json={"username": "ab", "password": "Cr3ated-pass"},
        ),
        400,
        "username shorter than three characters",
        "username",
    )
    expect_error(
        call(
            "POST",
            "/users",
            token=admin_token,
            json={"username": "bad name!", "password": "Cr3ated-pass"},
        ),
        400,
        "username with illegal characters",
        "username",
    )


def test_req1_user_list_hides_credentials(admin_token):
    """The paginated account list contains the new account but no hashes."""
    username = unique_username("listed")
    try:
        expect(
            call(
                "POST",
                "/users",
                token=admin_token,
                json={"username": username, "password": "Cr3ated-pass"},
            ),
            201,
            "create the account to list",
        )
        response = call("GET", "/users", token=admin_token, params={"page_size": 100})
        expect(response, 200, "list accounts")
        page = response.json()
        assert set(page) >= {"items", "page", "page_size", "total", "pages"}
        usernames = [item["username"] for item in page["items"]]
        assert username in usernames
        assert {"admin", "user"} <= set(usernames)
        for item in page["items"]:
            assert "password_hash" not in item
            assert "password" not in item
    finally:
        call("DELETE", f"/users/{username}", token=admin_token)


def test_req1_deactivation_blocks_access_and_reactivation_restores_it(
    admin_token, temp_user
):
    """Deactivation revokes access immediately and reactivation restores it."""
    token = temp_user["token"]
    expect(call("GET", "/auth/me", token=token), 200, "active account works")

    response = call(
        "PATCH",
        f"/users/{temp_user['username']}",
        token=admin_token,
        json={"is_active": False},
    )
    expect(response, 200, "deactivate the account")
    assert response.json().get("is_active") is False

    expect_error(
        call("GET", "/auth/me", token=token),
        403,
        "deactivated account uses an existing token",
        "deactivat",
    )
    expect_error(
        call(
            "POST",
            "/auth/login",
            json={
                "username": temp_user["username"],
                "password": temp_user["password"],
            },
        ),
        403,
        "deactivated account logs in",
        "deactivat",
    )

    response = call(
        "PATCH",
        f"/users/{temp_user['username']}",
        token=admin_token,
        json={"is_active": True},
    )
    expect(response, 200, "reactivate the account")
    assert response.json().get("is_active") is True
    expect(call("GET", "/auth/me", token=token), 200, "reactivated account works again")


def test_req1_admin_cannot_be_deactivated_or_deleted(admin_token):
    """The singleton admin account is protected from both operations (409)."""
    expect_error(
        call("PATCH", "/users/admin", token=admin_token, json={"is_active": False}),
        409,
        "deactivate the admin account",
        "administrator",
    )
    expect_error(
        call("DELETE", "/users/admin", token=admin_token),
        409,
        "delete the admin account",
        "administrator",
    )


def test_req1_user_cannot_manage_accounts(user_token):
    """A normal user gets 403 on every admin-only endpoint."""
    expect_error(
        call("GET", "/users", token=user_token),
        403,
        "list accounts as a normal user",
        "admin",
    )
    expect_error(
        call(
            "POST",
            "/users",
            token=user_token,
            json={"username": unique_username("nope"), "password": "Nope-pass"},
        ),
        403,
        "create accounts as a normal user",
        "admin",
    )
    expect_error(
        call("DELETE", "/users/user", token=user_token),
        403,
        "delete accounts as a normal user",
        "admin",
    )


def test_req1_delete_account(admin_token):
    """Deleting an account returns 204 and the account is gone (404)."""
    username = unique_username("deleted")
    expect(
        call(
            "POST",
            "/users",
            token=admin_token,
            json={"username": username, "password": "Cr3ated-pass"},
        ),
        201,
        "create the account to delete",
    )
    response = call("DELETE", f"/users/{username}", token=admin_token)
    expect(response, 204, "delete the account")
    assert response.content == b"", "a 204 response must not have a body"
    expect_error(
        call("GET", f"/users/{username}", token=admin_token),
        404,
        "read the deleted account",
        "not found",
    )

# ---------------------------------------------------------------------------
# Importing airports, airlines and routes
# ---------------------------------------------------------------------------


def test_req2_import_status_reports_counts(admin_token, dataset):
    """/import/status reports the row count of every dataset."""
    response = call("GET", "/import/status", token=admin_token)
    expect(response, 200, "GET /import/status")
    counts = dataset_counts(admin_token)
    assert counts["airlines"] == 15
    assert counts["airports"] == 46
    assert counts["routes"] == 260


def test_req2_import_single_dataset(admin_token, dataset):
    """Any single dataset can be imported alone and only it is replaced."""
    before = dataset_counts(admin_token)
    response = import_files(admin_token, "airlines")
    expect(response, 200, "import airlines.csv on its own")
    body = response.json()
    assert set(body) >= {"imported", "replaced", "counts", "message"}
    assert body["imported"]["airlines"] == 15
    assert "airlines" in body["replaced"]
    assert body["counts"] == before
    after = dataset_counts(admin_token)
    assert after == before, "airports and routes must be untouched by an airlines-only import"


def test_req2_import_all_datasets_together(admin_token, dataset):
    """The three CSV files can be uploaded in one multipart request."""
    response = import_files(admin_token, "airlines", "airports", "routes")
    expect(response, 200, "import all three datasets in one request")
    body = response.json()
    assert body["imported"] == DATASET_COUNTS
    assert body["counts"] == DATASET_COUNTS
    for name in ("airlines", "airports", "routes"):
        assert name in body["replaced"]
    assert isinstance(body["message"], str) and body["message"]


def test_req2_import_rejects_wrong_columns(admin_token, dataset):
    """A CSV whose header does not match the schema is rejected with 400."""
    # 'id' instead of 'airline_id': the first expected column is missing.
    text = "id,name,iata_code,icao_code,country\n1,Qantas,QF,QFA,Australia\n"
    before = dataset_counts(admin_token)
    response = import_csv_text(admin_token, "airlines", "airlines.csv", text)
    body = expect_error(response, 400, "airlines.csv with a wrong column name")
    assert "message" in body
    assert dataset_counts(admin_token) == before, "a rejected file must not change the DB"


def test_req2_import_requires_at_least_one_file(admin_token):
    """An import request without any file is a 400."""
    expect_error(
        call("POST", "/import", token=admin_token),
        400,
        "import request without a file",
    )


def test_req2_import_rejects_broken_references(admin_token, dataset):
    """An import that would break referential integrity is a 409.

    Only the first five airlines are imported while routes.csv still references
    airlines 6-15, so after applying the whole request some routes would point to
    airlines that no longer exist.  The request must be rejected *and* the
    database must be unchanged afterwards (atomicity).
    """
    before = dataset_counts(admin_token)
    header, rows = read_csv_rows(CSV_FILES["airlines"])
    subset = header + "".join(rows[:5])
    with open(CSV_FILES["routes"], "rb") as routes_handle:
        response = call(
            "POST",
            "/import",
            token=admin_token,
            files={
                "airlines": ("airlines.csv", io.BytesIO(subset.encode()), "text/csv"),
                "routes": ("routes.csv", routes_handle, "text/csv"),
            },
        )
    body = expect_error(response, 409, "import that breaks referential integrity")
    assert "message" in body
    after = dataset_counts(admin_token)
    assert after == before, "the rejected import must not change any dataset"


def test_req2_import_is_atomic(admin_token, dataset):
    """When one file in a multi-file request is invalid, nothing is written.

    The airlines file is a *valid* three-row document while the airports file is
    broken.  The whole request must fail (400) and the current airlines dataset
    must keep its 15 rows instead of being replaced by the three valid rows.
    """
    before = dataset_counts(admin_token)
    header, rows = read_csv_rows(CSV_FILES["airlines"])
    valid_subset = header + "".join(rows[:3])
    broken_airports = "airport_id,name\n1,Nowhere Airport\n"  # missing columns
    response = call(
        "POST",
        "/import",
        token=admin_token,
        files={
            "airlines": (
                "airlines.csv",
                io.BytesIO(valid_subset.encode()),
                "text/csv",
            ),
            "airports": (
                "airports.csv",
                io.BytesIO(broken_airports.encode()),
                "text/csv",
            ),
        },
    )
    expect_error(response, 400, "multi-file import with one broken file")
    after = dataset_counts(admin_token)
    assert after == before, "a failed import must be rolled back atomically"


def test_req2_import_requires_admin(user_token):
    """A normal user cannot import datasets (403)."""
    header, _rows = read_csv_rows(CSV_FILES["airlines"])
    response = call(
        "POST",
        "/import",
        token=user_token,
        files={
            "airlines": ("airlines.csv", io.BytesIO(header.encode()), "text/csv")
        },
    )
    expect_error(response, 403, "import as a normal user", "admin")

# ---------------------------------------------------------------------------
# Exploring airports, airlines and routes
# ---------------------------------------------------------------------------


def test_req3_airports_are_paginated(dataset, user_token):
    """Airport collections use the pagination envelope and validate page_size."""
    response = call(
        "GET", "/airports", token=user_token, params={"page": 1, "page_size": 5}
    )
    expect(response, 200, "GET /airports?page_size=5")
    page = response.json()
    assert set(page) >= {"items", "page", "page_size", "total", "pages"}
    assert page["total"] == 46
    assert page["page"] == 1
    assert page["page_size"] == 5
    assert page["pages"] == 10  # ceil(46 / 5)
    assert len(page["items"]) == 5
    assert all("iata_code" in item for item in page["items"])

    second = call(
        "GET", "/airports", token=user_token, params={"page": 2, "page_size": 5}
    )
    expect(second, 200, "GET /airports page 2")
    first_ids = {item["airport_id"] for item in page["items"]}
    second_ids = {item["airport_id"] for item in second.json()["items"]}
    assert first_ids.isdisjoint(second_ids), "pages must not overlap"

    expect_error(
        call("GET", "/airports", token=user_token, params={"page_size": 0}),
        400,
        "page_size below the minimum",
    )
    expect_error(
        call("GET", "/airports", token=user_token, params={"page_size": 101}),
        400,
        "page_size above the maximum",
    )


def test_req3_airport_search_is_case_insensitive(dataset, user_token):
    """`q=` searches airports case-insensitively and finds Sydney."""
    response = call(
        "GET",
        "/airports",
        token=user_token,
        params={"q": "sydney", "page_size": 100},
    )
    expect(response, 200, "search airports for 'sydney'")
    page = response.json()
    assert page["total"] >= 1
    assert any(item["iata_code"] == "SYD" for item in page["items"])
    for item in page["items"]:
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("name", "city", "country", "iata_code", "icao_code")
        ).lower()
        assert "sydney" in haystack


def test_req3_unknown_airport_is_404(dataset, user_token):
    """A well-formed but unknown IATA code returns 404."""
    body = expect_error(
        call("GET", "/airports/ZZZ", token=user_token),
        404,
        "read an airport that does not exist",
        "ZZZ",
    )
    assert body["code"] == 404


def test_req3_airport_routes_can_be_filtered_by_direction(dataset, user_token):
    """Airport routes filtered by direction always touch that airport."""
    departures = call(
        "GET",
        "/airports/SYD/routes",
        token=user_token,
        params={"direction": "departure", "page_size": 100},
    )
    expect(departures, 200, "SYD departure routes")
    page = departures.json()
    assert page["total"] == 22
    assert len(page["items"]) == 22
    for route in page["items"]:
        assert route["origin_iata"] == "SYD"
        assert route["destination_iata"] != "SYD"

    arrivals = call(
        "GET",
        "/airports/SYD/routes",
        token=user_token,
        params={"direction": "arrival", "page_size": 100},
    )
    expect(arrivals, 200, "SYD arrival routes")
    for route in arrivals.json()["items"]:
        assert route["destination_iata"] == "SYD"

    expect_error(
        call(
            "GET",
            "/airports/SYD/routes",
            token=user_token,
            params={"direction": "sideways"},
        ),
        400,
        "invalid direction filter",
    )


def test_req3_airline_routes_all_belong_to_the_airline(dataset, user_token):
    """/airlines/QF/routes only returns Qantas routes."""
    response = call(
        "GET", "/airlines/QF/routes", token=user_token, params={"page_size": 100}
    )
    expect(response, 200, "GET /airlines/QF/routes")
    page = response.json()
    assert page["total"] == 20
    assert len(page["items"]) == 20
    for route in page["items"]:
        assert route["airline_iata"] == "QF"


def test_req3_route_detail_embeds_related_objects(dataset, user_token):
    """A route detail embeds the airline and both airports."""
    response = call("GET", "/routes/1", token=user_token)
    expect(response, 200, "GET /routes/1")
    route = response.json()
    assert route["route_id"] == 1
    assert route["airline"]["iata_code"] == route["airline_iata"]
    assert route["airline"]["name"]
    assert route["origin_airport"]["iata_code"] == route["origin_iata"]
    assert route["destination_airport"]["iata_code"] == route["destination_iata"]
    expect_error(
        call("GET", "/routes/999999", token=user_token),
        404,
        "read a route that does not exist",
        "not found",
    )


def test_req3_routes_filter_by_max_stops(dataset, user_token):
    """`max_stops` never returns a route with more stops than requested."""
    no_stops = call(
        "GET", "/routes", token=user_token, params={"max_stops": 0, "page_size": 100}
    )
    expect(no_stops, 200, "GET /routes?max_stops=0")
    page = no_stops.json()
    assert page["total"] == 215
    assert all(route["stops"] == 0 for route in page["items"])

    one_stop = call(
        "GET", "/routes", token=user_token, params={"max_stops": 1, "page_size": 100}
    )
    expect(one_stop, 200, "GET /routes?max_stops=1")
    page = one_stop.json()
    assert page["total"] == 260  # every row of the provided CSV has 0 or 1 stop
    assert all(route["stops"] <= 1 for route in page["items"])

    expect_error(
        call("GET", "/routes", token=user_token, params={"max_stops": -1}),
        400,
        "negative max_stops",
    )


def test_req3_exploration_requires_authentication():
    """The exploration endpoints are protected like the rest of the API."""
    expect_error(call("GET", "/airports"), 401, "list airports without a token")
    expect_error(call("GET", "/routes"), 401, "list routes without a token")

# ---------------------------------------------------------------------------
# My travel plans
# ---------------------------------------------------------------------------


def test_req4_create_plan(temp_user, sample_routes):
    """Creating a plan returns 201 with dates and expanded routes."""
    route_ids = [sample_routes[0]["route_id"], sample_routes[1]["route_id"]]
    departure = date.today() + timedelta(days=30)
    response = create_plan(temp_user["token"], "Japan Spring Trip", 30, 10, route_ids)
    expect(response, 201, "create a travel plan")
    plan = response.json()
    assert plan["plan_id"] > 0
    assert plan["name"] == "Japan Spring Trip"
    assert plan["departure_date"] == departure.isoformat()
    assert plan["return_date"] == (departure + timedelta(days=10)).isoformat()
    assert plan["route_count"] == 2
    assert {route["route_id"] for route in plan["routes"]} == set(route_ids)
    for route in plan["routes"]:
        assert route["airline"]["name"]
        assert route["origin_airport"]["iata_code"]
        assert route["destination_airport"]["iata_code"]


def test_req4_invalid_date_range_rejected(temp_user):
    """A return date earlier than the departure date is a 400."""
    departure = date.today() + timedelta(days=20)
    response = call(
        "POST",
        "/plans",
        token=temp_user["token"],
        json={
            "name": "Backwards Trip",
            "departure_date": departure.isoformat(),
            "return_date": (departure - timedelta(days=1)).isoformat(),
        },
    )
    body = expect_error(response, 400, "return_date before departure_date")
    assert "request validation failed" in body["message"].lower()
    assert body.get("details"), "validation errors should explain the failing field"
    assert body["details"][0].get("field") == "return_date"
    assert "earlier" in body["details"][0].get("issue", "").lower()


def test_req4_duplicate_plan_name_conflict(temp_user, user_token):
    """Plan names are unique per account, but two accounts may share one."""
    expect(create_plan(temp_user["token"], "Duplicate Name", 10, 2), 201, "first plan")
    expect_error(
        create_plan(temp_user["token"], "Duplicate Name", 20, 2),
        409,
        "same plan name for the same account",
        "already",
    )
    # A different account is allowed to use the very same name.
    other = create_plan(user_token, "Duplicate Name", 10, 2)
    expect(other, 201, "same plan name for another account")
    other_plan_id = other.json()["plan_id"]
    try:
        assert other.json()["name"] == "Duplicate Name"
    finally:
        call("DELETE", f"/plans/{other_plan_id}", token=user_token)


def test_req4_plans_are_private(temp_user, admin_token, user_token):
    """Plan lists and details only expose the caller's own plans."""
    created = create_plan(temp_user["token"], "Private Trip", 15, 4)
    expect(created, 201, "create a private plan")
    plan_id = created.json()["plan_id"]

    own_page = call("GET", "/plans", token=temp_user["token"])
    expect(own_page, 200, "owner lists their plans")
    assert own_page.json()["total"] == 1
    assert own_page.json()["items"][0]["plan_id"] == plan_id

    for token, label in ((admin_token, "admin"), (user_token, "another user")):
        page = call("GET", "/plans", token=token, params={"page_size": 100})
        expect(page, 200, f"{label} lists plans")
        ids = [plan["plan_id"] for plan in page.json()["items"]]
        assert plan_id not in ids
        expect_error(
            call("GET", f"/plans/{plan_id}", token=token),
            404,
            f"{label} reads somebody else's plan",
            "not found",
        )


def test_req4_patch_plan_dates(temp_user):
    """PATCH updates only the supplied dates and re-validates the range."""
    created = create_plan(temp_user["token"], "Patch Me", 30, 10)
    expect(created, 201, "create a plan to patch")
    plan_id = created.json()["plan_id"]

    # Still before the unchanged return date (departure + 35 < return + 40).
    new_departure = date.today() + timedelta(days=35)
    response = call(
        "PATCH",
        f"/plans/{plan_id}",
        token=temp_user["token"],
        json={"departure_date": new_departure.isoformat()},
    )
    expect(response, 200, "patch the departure date")
    plan = response.json()
    assert plan["name"] == "Patch Me", "omitted fields must keep their value"
    assert plan["departure_date"] == new_departure.isoformat()

    body = expect_error(
        call(
            "PATCH",
            f"/plans/{plan_id}",
            token=temp_user["token"],
            json={"departure_date": (date.today() + timedelta(days=90)).isoformat()},
        ),
        400,
        "patch that puts departure after the unchanged return date",
    )
    assert body["details"][0]["field"] == "return_date"


def test_req4_add_and_remove_routes(temp_user, sample_routes):
    """Routes can be added idempotently and removed again."""
    route_ids = [route["route_id"] for route in sample_routes[:3]]
    created = create_plan(temp_user["token"], "Route Builder", 20, 6, [route_ids[0]])
    expect(created, 201, "create a plan with one route")
    plan_id = created.json()["plan_id"]

    response = call(
        "POST",
        f"/plans/{plan_id}/routes",
        token=temp_user["token"],
        json={"route_ids": route_ids[1:]},
    )
    expect(response, 200, "add two routes")
    plan = response.json()
    assert {route["route_id"] for route in plan["routes"]} == set(route_ids)

    # Adding an existing route again is idempotent, not a conflict.
    again = call(
        "POST",
        f"/plans/{plan_id}/routes",
        token=temp_user["token"],
        json={"route_ids": [route_ids[0]]},
    )
    expect(again, 200, "re-add an existing route")
    assert again.json()["route_count"] == 3

    removed = call(
        "DELETE",
        f"/plans/{plan_id}/routes/{route_ids[1]}",
        token=temp_user["token"],
    )
    expect(removed, 204, "remove one route from the plan")
    routes = call("GET", f"/plans/{plan_id}/routes", token=temp_user["token"])
    expect(routes, 200, "list the remaining routes")
    remaining = [route["route_id"] for route in routes.json()["items"]]
    assert route_ids[1] not in remaining
    assert set(remaining) == {route_ids[0], route_ids[2]}

    expect_error(
        call(
            "DELETE",
            f"/plans/{plan_id}/routes/{route_ids[1]}",
            token=temp_user["token"],
        ),
        404,
        "remove a route that is not part of the plan",
        "not part",
    )

    expect_error(
        call(
            "POST",
            f"/plans/{plan_id}/routes",
            token=temp_user["token"],
            json={"route_ids": [999999]},
        ),
        404,
        "add a route that does not exist",
    )


def test_req4_plan_routes_expand(temp_user, sample_routes):
    """`expand=true` embeds the full airline and airports of every route."""
    route_ids = [route["route_id"] for route in sample_routes[:2]]
    created = create_plan(temp_user["token"], "Expandable", 25, 3, route_ids)
    expect(created, 201, "create a plan with two routes")
    plan_id = created.json()["plan_id"]

    compact = call("GET", f"/plans/{plan_id}/routes", token=temp_user["token"])
    expect(compact, 200, "list plan routes without expansion")
    for route in compact.json()["items"]:
        assert "airline" not in route

    expanded = call(
        "GET",
        f"/plans/{plan_id}/routes",
        token=temp_user["token"],
        params={"expand": "true"},
    )
    expect(expanded, 200, "list plan routes with expand=true")
    items = expanded.json()["items"]
    assert len(items) == 2
    for route in items:
        assert route["airline"]["name"]
        assert route["origin_airport"]["iata_code"] == route["origin_iata"]
        assert route["destination_airport"]["iata_code"] == route["destination_iata"]


def test_req4_delete_plan(temp_user):
    """Deleting a plan returns 204 and it can no longer be fetched."""
    created = create_plan(temp_user["token"], "Delete Me", 12, 2)
    expect(created, 201, "create a plan to delete")
    plan_id = created.json()["plan_id"]
    expect(
        call("DELETE", f"/plans/{plan_id}", token=temp_user["token"]),
        204,
        "delete the plan",
    )
    expect_error(
        call("GET", f"/plans/{plan_id}", token=temp_user["token"]),
        404,
        "read the deleted plan",
        "not found",
    )


def test_req4_plans_require_authentication():
    """The plan endpoints reject unauthenticated requests with 401."""
    expect_error(call("GET", "/plans"), 401, "list plans without a token")
    expect_error(
        call(
            "POST",
            "/plans",
            json={
                "name": "Nope",
                "departure_date": date.today().isoformat(),
                "return_date": date.today().isoformat(),
            },
        ),
        401,
        "create a plan without a token",
    )

# ---------------------------------------------------------------------------
# Exporting travel plans
# ---------------------------------------------------------------------------


def test_req5_json_export_is_a_self_contained_download(temp_user, sample_routes):
    """JSON export is a downloadable, self-contained, date-ordered document."""
    route_ids = [route["route_id"] for route in sample_routes[:2]]
    expected_names = set()
    for offset in (40, 10, 25):  # deliberately created out of order
        name = f"Export Trip {offset}"
        expect(create_plan(temp_user["token"], name, offset, 4, route_ids), 201, name)
        expected_names.add(name)

    response = call(
        "GET",
        "/plans/export",
        token=temp_user["token"],
        params={"format": "json"},
    )
    expect(response, 200, "JSON export")
    assert response.headers["Content-Type"].startswith("application/json")
    disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in disposition, disposition
    assert f'filename="travel_plans_{temp_user["username"]}.json"' in disposition

    document = response.json()
    assert document["account"] == temp_user["username"]
    assert isinstance(document["exported_at"], str)
    assert document["exported_at"].endswith("Z")
    assert document["plan_count"] == 3
    assert {plan["name"] for plan in document["plans"]} == expected_names

    dates = [plan["departure_date"] for plan in document["plans"]]
    assert dates == sorted(dates), "plans must be ordered by departure_date ascending"

    for plan in document["plans"]:
        assert plan["routes"], "the export must embed the plan routes"
        for route in plan["routes"]:
            # Full objects, not ids: the file must be usable offline.
            assert route["airline"]["name"]
            assert route["airline"]["iata_code"] == route["airline_iata"]
            assert (
                route["origin_airport"]["iata_code"] == route["origin_iata"]
            )
            assert (
                route["destination_airport"]["iata_code"]
                == route["destination_iata"]
            )


def test_req5_json_export_of_an_empty_account(temp_user):
    """An account without plans gets a 200 with an empty plans array."""
    response = call(
        "GET",
        "/plans/export",
        token=temp_user["token"],
        params={"format": "json"},
    )
    expect(response, 200, "JSON export for an empty account")
    document = response.json()
    assert document["account"] == temp_user["username"]
    assert document["plan_count"] == 0
    assert document["plans"] == []


def test_req5_image_export_returns_a_png(temp_user):
    """Format=image returns an inline PNG rendering of future plans."""
    expect(
        create_plan(temp_user["token"], "上海-东京 春节深度游", 15, 6),
        201,
        "create a future plan",
    )
    response = call(
        "GET",
        "/plans/export",
        token=temp_user["token"],
        params={"format": "image"},
    )
    expect(response, 200, "PNG export")
    assert response.headers["Content-Type"].startswith("image/png")
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n", "body must be a real PNG"
    assert len(response.content) > 5000, "the rendered timeline looks suspiciously small"
    width, height = struct.unpack(">II", response.content[16:24])
    assert width > 100 and height > 100, (width, height)


def test_req5_image_export_without_future_plans_is_404(temp_user):
    """An account with only past plans gets a 404 JSON error for the image."""
    past_departure = date.today() - timedelta(days=20)
    response = call(
        "POST",
        "/plans",
        token=temp_user["token"],
        json={
            "name": "Past Trip",
            "departure_date": past_departure.isoformat(),
            "return_date": (past_departure + timedelta(days=5)).isoformat(),
        },
    )
    expect(response, 201, "create a plan in the past")
    body = expect_error(
        call(
            "GET",
            "/plans/export",
            token=temp_user["token"],
            params={"format": "image"},
        ),
        404,
        "image export without any future plan",
        "no upcoming travel plans",
    )
    assert body["code"] == 404


def test_req5_accept_header_negotiation(temp_user):
    """Accept: image/png selects the image, ?format= overrides Accept."""
    expect(create_plan(temp_user["token"], "Negotiated Trip", 12, 3), 201, "future plan")
    png = call(
        "GET",
        "/plans/export",
        token=temp_user["token"],
        headers={"Accept": "image/png"},
    )
    expect(png, 200, "export negotiated through Accept: image/png")
    assert png.headers["Content-Type"].startswith("image/png")
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    document = call(
        "GET",
        "/plans/export",
        token=temp_user["token"],
        headers={"Accept": "image/png"},
        params={"format": "json"},
    )
    expect(document, 200, "?format=json overrides Accept: image/png")
    assert document.headers["Content-Type"].startswith("application/json")


def test_req5_export_only_contains_own_plans(temp_user, admin_token, user_token):
    """Exporting never leaks another account's plans (admin included)."""
    created = create_plan(temp_user["token"], "Secret Export", 8, 2)
    expect(created, 201, "create a private plan")
    plan_id = created.json()["plan_id"]
    for token, label in ((user_token, "user"), (admin_token, "admin")):
        response = call("GET", "/plans/export", token=token, params={"format": "json"})
        expect(response, 200, f"export as {label}")
        exported_ids = [plan["plan_id"] for plan in response.json()["plans"]]
        assert plan_id not in exported_ids


def test_req5_export_requires_authentication():
    """The export endpoint requires a valid bearer token (401)."""
    expect_error(call("GET", "/plans/export"), 401, "export without a token")


def test_req5_invalid_export_format_is_400(temp_user):
    """An unsupported format value is rejected with a 400."""
    expect_error(
        call(
            "GET",
            "/plans/export",
            token=temp_user["token"],
            params={"format": "csv"},
        ),
        400,
        "export with an unsupported format",
        "format",
    )

# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


def test_boundary_unknown_plan_id(temp_user):
    """An unknown plan id returns 404 with the standard error envelope."""
    body = expect_error(
        call("GET", "/plans/999999", token=temp_user["token"]),
        404,
        "read an unknown plan id",
        "not found",
    )
    assert body["code"] == 404


def test_boundary_malformed_json_body(temp_user):
    """A malformed JSON request body is a 400, not a server error."""
    response = call(
        "POST",
        "/plans",
        token=temp_user["token"],
        data='{"name": "Unclosed", ',
        headers={"Content-Type": "application/json"},
    )
    expect_error(response, 400, "create a plan with malformed JSON", "json")

# Persistence: every assertion in this file reads the state back through the API,
# so a pass means the data really survived the round-trip to ``airtrip.db``.