def auth_headers(client, email="test@example.com", full_name="Test User"):
    client.post(
        "/auth/register",
        json={"full_name": full_name, "email": email, "password": "strongpassword123"},
    )
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "strongpassword123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["gemini_configured"] is False


def test_root_and_openapi(client):
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["docs"] == "/docs"

    docs = client.get("/openapi.json")
    assert docs.status_code == 200
    paths = docs.json()["paths"]
    assert "/planners/home" in paths
    assert "/planners/party" in paths
    assert "/planners/jewelry" in paths
    assert "/planners/jewelry-upload" in paths
    assert "/auth/register" in paths


def test_register_login_me_logout(client):
    headers = auth_headers(client)

    session = client.get("/session-info", headers=headers)
    assert session.status_code == 200
    assert session.json()["user"]["email"] == "test@example.com"

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["full_name"] == "Test User"

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    me_after_logout = client.get("/auth/me", headers=headers)
    assert me_after_logout.status_code == 401


def test_swagger_oauth_token_route(client):
    client.post(
        "/auth/register",
        json={"full_name": "Token User", "email": "token@example.com", "password": "strongpassword123"},
    )
    response = client.post(
        "/auth/token",
        data={"username": "token@example.com", "password": "strongpassword123"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_home_planner_and_history(client):
    headers = auth_headers(client, "planner@example.com", "Planner User")
    payload = {
        "budget": 100000,
        "rooms": ["Living Room"],
        "items": [
            {"name": "Sofa", "quantity": 1, "preferred_style": "Modern"},
            {"name": "Ceiling Light", "quantity": 2, "preferred_style": "Minimal"},
        ],
        "city": "Chennai",
        "style": "Modern",
    }
    planner = client.post("/planners/home", json=payload, headers=headers)
    assert planner.status_code == 200
    data = planner.json()
    assert data["planner_type"] == "home"
    assert data["ai_used"] is False
    assert data["history_id"] is not None
    assert len(data["recommendations"]) >= 1
    assert data["estimated_total"] <= data["budget"] + 0.01

    history = client.get("/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == 1

    session_data = client.get("/session-data", headers=headers)
    assert session_data.status_code == 200
    assert session_data.json()["logged_in"] is True


def test_party_planner_and_compatibility_route(client):
    headers = auth_headers(client, "party@example.com", "Party User")
    response = client.post(
        "/planners/party",
        json={
            "budget": 50000,
            "guest_count": 80,
            "event_type": "Birthday",
            "city": "Chennai",
            "food_preference": "Vegetarian",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["planner_type"] == "party"

    compat = client.post(
        "/generate-party",
        json={
            "budget": 20000,
            "guest_count": 30,
            "event_type": "Birthday",
        },
        headers=headers,
    )
    assert compat.status_code == 200
    assert compat.json()["planner_type"] == "party"


def test_jewelry_json_route(client):
    headers = auth_headers(client, "jewelry-json@example.com", "Jewelry JSON")
    response = client.post(
        "/planners/jewelry",
        json={
            "budget": 10000,
            "occasion": "Wedding",
            "style": "Elegant",
            "metal_preference": "Gold",
            "outfit_color": "Maroon",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["planner_type"] == "jewelry"
    assert response.json()["ai_used"] is False


def test_jewelry_upload_route(client):
    headers = auth_headers(client, "jewelry-upload@example.com", "Jewelry Upload")
    # Minimal valid PNG (1x1 RGBA)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c6360000000020001e221bc330000000049454e44ae426082"
    )
    response = client.post(
        "/planners/jewelry-upload",
        data={
            "budget": "10000",
            "occasion": "Wedding",
            "style": "Elegant",
            "metal_preference": "Gold",
            "outfit_color": "Maroon",
        },
        files={"outfit_image": ("outfit.png", png, "image/png")},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["planner_type"] == "jewelry"
    assert response.json()["ai_used"] is False


def test_bad_image_type_is_rejected(client):
    headers = auth_headers(client, "bad-image@example.com", "Bad Image")
    response = client.post(
        "/generate-jewelry",
        data={"budget": "10000", "occasion": "Wedding"},
        files={"outfit_image": ("outfit.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 415


def test_duplicate_register_is_rejected(client):
    payload = {
        "full_name": "Duplicate User",
        "email": "duplicate@example.com",
        "password": "strongpassword123",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409
