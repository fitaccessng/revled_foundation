from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def test_vanguard_mentor_signup_page_loads():
    client = server.app.test_client()
    response = client.get('/vanguard-hub/mentor-signup')
    assert response.status_code == 200
    assert b'Become a Vanguard Industry Mentor' in response.data


def test_catalyst_mentor_page_loads_as_its_own_page():
    client = server.app.test_client()
    response = client.get('/catalyst/volunteer-mentor')
    assert response.status_code == 200
    assert b'Volunteer or Mentor with Catalyst' in response.data


def test_vanguard_mentor_page_is_not_redirected_to_catalyst_pipeline():
    client = server.app.test_client()
    response = client.get('/vanguard-hub/mentor-signup')
    assert response.status_code == 200
    assert b'Catalyst pipeline' not in response.data


def test_hub_login_links_to_working_forgot_password_route():
    client = server.app.test_client()
    response = client.get('/hub/login')
    assert response.status_code == 200
    assert b'href="/hub/forgot-password"' in response.data
    assert b'action="/hub/login"' in response.data


def test_admin_mentor_signups_page_requires_admin():
    client = server.app.test_client()
    response = client.get('/admin/vanguard-mentor-signups', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/login')


def test_locked_library_item_is_visible_but_not_accessible_until_release_date():
    member = {
        'membership_tier': 'FULL_ACCESS',
        'user_type': 'ENTREPRENEUR',
    }
    item = {
        'content_type': 'resources',
        'access_tier': 'ALL',
        'audience_user_types': 'ALL',
        'starts_at': '2999-12-31 00:00:00',
        'is_published': 1,
    }

    assert server.hub_member_can_see(member, item) is True
    assert server.hub_member_can_access(member, item) is False
    assert server.is_hub_content_released(item) is False
