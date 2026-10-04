"""
Tests for database models, user sessions, Google auth endpoints, and base resume management.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.web_app import app
from src.database import (
    upsert_user,
    create_session,
    get_user_by_session,
    delete_session,
    save_user_profile,
    get_user_profile,
    set_user_profile_active,
    delete_user_profile,
    save_user_base_resume,
    get_user_base_resume,
    set_user_base_resume_active,
    delete_user_base_resume,
    check_rate_limit,
    increment_daily_usage,
)

client = TestClient(app)


def test_database_user_and_session():
    test_gid = "test_google_user_999"
    user = upsert_user(test_gid, "unit_tester@example.com", "Unit Tester", "https://pic.jpg")
    assert user["google_id"] == test_gid
    assert user["email"] == "unit_tester@example.com"

    # Create session
    token = create_session(test_gid)
    retrieved = get_user_by_session(token)
    assert retrieved is not None
    assert retrieved["email"] == "unit_tester@example.com"

    # Delete session
    delete_session(token)
    assert get_user_by_session(token) is None


def test_database_user_profile():
    test_gid = "test_google_user_888"
    upsert_user(test_gid, "profile_tester@example.com")

    sample_prof = {"personal": {"full_name": "Test Tester"}}
    save_user_profile(test_gid, sample_prof, is_active=True)

    data = get_user_profile(test_gid)
    assert data is not None
    assert data["profile"]["personal"]["full_name"] == "Test Tester"
    assert data["is_active"] is True

    # Toggle active
    set_user_profile_active(test_gid, False)
    data = get_user_profile(test_gid)
    assert data["is_active"] is False

    # Delete
    delete_user_profile(test_gid)
    assert get_user_profile(test_gid) is None


def test_database_base_resume(tmp_path):
    test_gid = "test_google_user_777"
    upsert_user(test_gid, "resume_tester@example.com")

    dummy_file = tmp_path / "my_base.pdf"
    dummy_file.write_text("dummy resume content")

    save_user_base_resume(
        google_id=test_gid,
        filename="my_base.pdf",
        file_path=str(dummy_file),
        file_ext=".pdf",
        is_active=True,
    )

    base = get_user_base_resume(test_gid)
    assert base is not None
    assert base["filename"] == "my_base.pdf"
    assert base["is_active"] is True

    # Toggle active
    set_user_base_resume_active(test_gid, False)
    base = get_user_base_resume(test_gid)
    assert base["is_active"] is False

    # Delete
    delete_user_base_resume(test_gid)
    assert get_user_base_resume(test_gid) is None


def test_database_base_resume_auto_reconstruction(tmp_path):
    test_gid = "test_reconstruct_user_123"
    upsert_user(test_gid, "reconstruct@example.com")

    dummy_file = tmp_path / "cloud_base.pdf"
    dummy_file.write_text("precious resume content across reboots")

    save_user_base_resume(
        google_id=test_gid,
        filename="cloud_base.pdf",
        file_path=str(dummy_file),
        file_ext=".pdf",
        is_active=True,
    )

    # Simulate container rebuild / wiped ephemeral disk:
    dummy_file.unlink()
    assert not dummy_file.exists()

    # get_user_base_resume should seamlessly reconstruct the file from DB bytes!
    base = get_user_base_resume(test_gid)
    assert base is not None
    assert base["filename"] == "cloud_base.pdf"
    reconstructed_path = Path(base["file_path"])
    assert reconstructed_path.exists()
    assert reconstructed_path.read_text() == "precious resume content across reboots"

    # Clean up
    delete_user_base_resume(test_gid)
    assert get_user_base_resume(test_gid) is None


def test_auth_config_endpoint():
    res = client.get("/api/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert "google_client_id" in data
    assert "apps.googleusercontent.com" in data["google_client_id"]


def test_auth_me_guest_and_user():
    # Guest request
    res_guest = client.get("/api/auth/me")
    assert res_guest.status_code == 200
    guest_data = res_guest.json()
    assert guest_data["is_authenticated"] is False
    assert "rate_limit" in guest_data

    # User request with valid session token
    test_gid = "test_google_user_666"
    upsert_user(test_gid, "session_tester@example.com", "Session Tester")
    token = create_session(test_gid)

    res_user = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_user.status_code == 200
    user_data = res_user.json()
    assert user_data["is_authenticated"] is True
    assert user_data["user"]["email"] == "session_tester@example.com"
    assert user_data["rate_limit"]["limit"] == 5

    # Logout
    res_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res_logout.status_code == 200

    # After logout, should be guest
    res_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_after.json()["is_authenticated"] is False


def test_deep_boost_limit_and_guest_rejection():
    import uuid
    from src.database import check_deep_boost_limit, increment_deep_boost_usage

    gid = f"deep_user_{uuid.uuid4().hex[:8]}"
    upsert_user(gid, f"{gid}@example.com", "Deep Tester")
    
    # Initial status
    status = check_deep_boost_limit(gid)
    assert status["allowed"] is True
    assert status["limit"] == 1
    assert status["remaining"] == 1

    # Guest trying to run 5-pass tournament gets 403
    res_guest = client.post(
        "/api/tailor",
        data={
            "jd_text": "Need software engineer with Python.",
            "tournament_passes": "5",
        }
    )
    assert res_guest.status_code == 403
    assert "exclusive to signed-in accounts" in res_guest.json()["detail"].lower()

    # Increment usage for user
    increment_deep_boost_usage(gid)
    status_after = check_deep_boost_limit(gid)
    assert status_after["allowed"] is False
    assert status_after["remaining"] == 0

    # User trying to run 5-pass tournament with exhausted quota gets 429
    token = create_session(gid)
    res_user = client.post(
        "/api/tailor",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "jd_text": "Need software engineer with Python.",
            "tournament_passes": "5",
        }
    )
    assert res_user.status_code == 429
    assert "deep quality boost" in res_user.json()["detail"].lower()


def test_admin_portal_and_quota_management():
    import uuid
    from src.database import (
        verify_admin_secret_key,
        check_rate_limit,
        check_deep_boost_limit,
        increment_daily_usage,
        increment_deep_boost_usage,
        ADMIN_GOOGLE_ID,
    )

    # 1. Admin login verification
    assert verify_admin_secret_key("1901") is True
    assert verify_admin_secret_key("wrong_key") is False

    res_login_bad = client.post("/api/admin/login", json={"secret_key": "wrong_key"})
    assert res_login_bad.status_code == 401

    res_login_ok = client.post("/api/admin/login", json={"secret_key": "1901"})
    assert res_login_ok.status_code == 200
    login_data = res_login_ok.json()
    admin_token = login_data["session_token"]
    assert login_data["user"]["google_id"] == ADMIN_GOOGLE_ID
    assert login_data["user"]["is_admin"] is True

    # 2. Admin dashboard access
    res_dash_page = client.get("/admin")
    assert res_dash_page.status_code == 200

    # Unauthorized access to admin API
    res_unauth = client.get("/api/admin/users")
    assert res_unauth.status_code == 403

    # Authorized access to admin API
    res_auth = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_auth.status_code == 200
    dash_data = res_auth.json()
    assert "users" in dash_data
    assert "guests" in dash_data
    assert "stats" in dash_data

    # 3. Create a test user and exhaust quotas
    user_gid = f"target_user_{uuid.uuid4().hex[:8]}"
    upsert_user(user_gid, f"{user_gid}@example.com", "Quota Target")
    user_id = f"user:{user_gid}"

    # Use 5 tailors
    for _ in range(5):
        increment_daily_usage(user_id)
    # Use 1 deep boost
    increment_deep_boost_usage(user_gid)

    # Check that user is locked
    user_limit = check_rate_limit(user_id, is_authenticated=True)
    assert user_limit["remaining"] == 0
    assert user_limit["allowed"] is False

    user_deep = check_deep_boost_limit(user_gid)
    assert user_deep["remaining"] == 0
    assert user_deep["allowed"] is False

    # 4. Admin resets tailoring quota
    res_reset_tailors = client.post(
        "/api/admin/user/reset-tailors",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"identifier": user_id}
    )
    assert res_reset_tailors.status_code == 200
    user_limit_after = check_rate_limit(user_id, is_authenticated=True)
    assert user_limit_after["allowed"] is True
    assert user_limit_after["remaining"] == 5

    # 5. Admin adds 3 bonus tailors
    res_add_tailors = client.post(
        "/api/admin/user/add-tailors",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"identifier": user_id, "count": 3}
    )
    assert res_add_tailors.status_code == 200
    user_limit_bonus = check_rate_limit(user_id, is_authenticated=True)
    assert user_limit_bonus["remaining"] == 8

    # 5b. Admin subtracts 2 tailors
    res_sub_tailors = client.post(
        "/api/admin/user/add-tailors",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"identifier": user_id, "count": -2}
    )
    assert res_sub_tailors.status_code == 200
    user_limit_sub = check_rate_limit(user_id, is_authenticated=True)
    assert user_limit_sub["remaining"] == 6

    # 6. Admin unlocks Deep Quality Boost
    res_reset_deep = client.post(
        "/api/admin/user/reset-deep-boost",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"google_id": user_gid}
    )
    assert res_reset_deep.status_code == 200
    user_deep_after = check_deep_boost_limit(user_gid)
    assert user_deep_after["allowed"] is True
    assert user_deep_after["remaining"] == 1

    # 6b. Admin adds another Deep Quality Boost (+1 -> total 2)
    res_adj_deep_pos = client.post(
        "/api/admin/user/adjust-deep-boost",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"google_id": user_gid, "count": 1}
    )
    assert res_adj_deep_pos.status_code == 200
    user_deep_pos = check_deep_boost_limit(user_gid)
    assert user_deep_pos["remaining"] == 2

    # 6c. Admin subtracts 1 Deep Quality Boost (-1 -> total 1)
    res_adj_deep_neg = client.post(
        "/api/admin/user/adjust-deep-boost",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"google_id": user_gid, "count": -1}
    )
    assert res_adj_deep_neg.status_code == 200
    user_deep_neg = check_deep_boost_limit(user_gid)
    assert user_deep_neg["remaining"] == 1

    # 7. Admin unlimited quota verification
    admin_limit = check_rate_limit(f"user:{ADMIN_GOOGLE_ID}", is_authenticated=True)
    assert admin_limit["allowed"] is True
    assert admin_limit["remaining"] >= 999999
    assert admin_limit["is_admin"] is True

    admin_deep = check_deep_boost_limit(ADMIN_GOOGLE_ID)
    assert admin_deep["allowed"] is True
    assert admin_deep["remaining"] >= 999999
    assert admin_deep["is_admin"] is True


def test_google_auth_endpoint(monkeypatch):
    from google.oauth2 import id_token

    # Verify invalid token returns 401, NOT 500
    res_bad = client.post("/api/auth/google", json={"credential": "invalid_jwt_token"})
    assert res_bad.status_code == 401

    # Mock verify_oauth2_token to return valid payload
    mock_payload = {
        "sub": "mock_google_user_555",
        "email": "shaked_test@example.com",
        "name": "Shaked Test",
        "picture": "https://lh3.googleusercontent.com/pic.jpg",
    }
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: mock_payload)

    res_good = client.post("/api/auth/google", json={"credential": "fake_valid_jwt"})
    assert res_good.status_code == 200
    data = res_good.json()
    assert data["status"] == "success"
    assert data["user"]["email"] == "shaked_test@example.com"
    assert "session_token" in data
    assert "rate_limit" in data


def test_tailor_endpoint_client_ip_and_validation():
    # Valid request structure reaches rate limit check with client_ip and validates file presence without 500 NameError
    res_no_file = client.post(
        "/api/tailor",
        data={"jd_text": "Software engineer needed with Python and React expertise."}
    )
    assert res_no_file.status_code == 400
    assert "Please upload your resume file" in res_no_file.json()["detail"]


def test_user_ip_linking_and_guest_exclusion():
    from src.database import (
        upsert_user,
        link_user_ip,
        get_linked_ips_for_user,
        list_active_guests_with_daily_usage,
        increment_daily_usage,
        get_system_stats,
    )
    gid = "unique_registered_user_ip_test"
    ip = "192.168.1.105"
    upsert_user(gid, f"{gid}@example.com", "IP Tester")

    # Record usage under guest IP first
    increment_daily_usage(f"ip:{ip}")

    # Now link IP to registered user
    link_user_ip(gid, ip)
    linked = get_linked_ips_for_user(gid)
    assert ip in linked

    # Guest table should exclude this IP because it is linked to a registered user
    guests = list_active_guests_with_daily_usage()
    guest_ips = [g["ip_address"] for g in guests]
    assert ip not in guest_ips

    # System stats should not count this registered user's IP as an active guest
    stats = get_system_stats()
    assert all(g["ip_address"] != ip for g in guests)


def test_cumulative_telemetry_preserved_after_admin_resets():
    import uuid
    from src.database import (
        record_tailor_run,
        get_system_stats,
        admin_reset_daily_usage,
        admin_adjust_tailors,
        admin_reset_deep_boost,
        check_rate_limit,
        check_deep_boost_limit,
        increment_daily_usage,
        increment_deep_boost_usage,
    )
    test_id = f"user_{uuid.uuid4().hex[:8]}"
    date_str = "2026-10-03"

    # Simulate 4 runs today for this user
    for _ in range(4):
        increment_daily_usage(f"user:{test_id}", date_str=date_str)
        record_tailor_run(
            identifier=f"user:{test_id}",
            client_ip="10.0.0.99",
            google_id=test_id,
            is_deep_boost=False,
            date_str=date_str,
        )

    # Simulate 1 deep boost run today
    increment_deep_boost_usage(test_id)
    record_tailor_run(
        identifier=f"user:{test_id}:deep_boost",
        client_ip="10.0.0.99",
        google_id=test_id,
        is_deep_boost=True,
        date_str=date_str,
    )

    stats_before = get_system_stats(date_str)
    assert stats_before["today_tailors"] >= 4
    assert stats_before["today_deep_boosts"] >= 1

    # Admin gives +2 tailors
    admin_adjust_tailors(f"user:{test_id}", delta=2, date_str=date_str)
    stats_after_add = get_system_stats(date_str)
    # Telemetry is unchanged!
    assert stats_after_add["today_tailors"] == stats_before["today_tailors"]

    # Admin resets daily usage
    admin_reset_daily_usage(f"user:{test_id}", date_str=date_str)
    stats_after_reset = get_system_stats(date_str)
    # Telemetry MUST NOT decrease or be wiped out!
    assert stats_after_reset["today_tailors"] == stats_before["today_tailors"]

    # Admin resets deep boost
    admin_reset_deep_boost(test_id, date_str=date_str)
    stats_after_deep_reset = get_system_stats(date_str)
    assert stats_after_deep_reset["today_deep_boosts"] == stats_before["today_deep_boosts"]




