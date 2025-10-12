#!/usr/bin/env python3

import datetime
import http
import json
import os
import urllib.parse
import re
import subprocess
import sys
import time

import requests

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(THIS_DIR, '..', 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
COURSES_FILE = os.path.join(DATA_DIR, 'courses.json')
ASSIGNMENTS_FILE = os.path.join(DATA_DIR, 'assignments.json')
SUBMISSIONS_FILE = os.path.join(DATA_DIR, 'submissions.json')

SERVER = 'http://127.0.0.1:3000'
API_BASE = 'api/v1'

SITE_ADMIN_ACCOUNT_ID = 2
SERVER_OWNER_ACCOUNT_ID = 1
SERVER_OWNER_USER_ID = 1

START_WAIT_ATTEMPTS = 5
START_WAIT_TIME_SECS = 5.0

# The randomly generated user tokens will be replaced in the database with these static tokens.
# This makes it much easier for those using the image to consistently access the API.
# Format: {user_name: (crypted_token, token_hint, crypted_refresh_token), ...}
STATIC_TOKENS = {
    'course-admin': {
        'cleartext': 'nHRkQ39czXL2x7xxKrPYmvtYTyWJCCHCVRMZTfTfZtJZZWXHnkN9UhnCy37XuYeK',
        'crypted_token': '1d5d351144b450103987ebbfbb5bc6469100e9e2',
        'token_hint': 'nHRkQ',
        'crypted_refresh_token': '3d0208181a1222fe9efc038e8f931d119c9d756e',
    },
    'course-grader': {
        'cleartext': 'uwRzuhDzDyEJBuJ8QR8PRTLAZHRU7ErY6aTtACNtB7tHZNVzLLw2AGZTGLQya9YX',
        'crypted_token': '0732aee101e43c7d51a8fec4b501969cec9d8cdf',
        'token_hint': 'uwRzu',
        'crypted_refresh_token': '0d4916b1834b3095debc3ef7803f000bbbe23b34',
    },
    'course-other': {
        'cleartext': 'VntnXWUfHDYDGhFV8VPmUrMEVuwJ3JeJ898FFDf7DHkGJ7vmrEW3eJx9cuHukh94',
        'crypted_token': '2adbb6db49400361b5c2702ec1090ba3c055f015',
        'token_hint': 'VntnX',
        'crypted_refresh_token': '9257719047b8a31c649ed2e1f871ca66cfdf3ac5',
    },
    'course-owner': {
        'cleartext': 'xkC8V8BWX4RFx7JMYyZuyDvtDAKRxuGHRxTR268eHzXCPYU46vw89DrBADat4n6U',
        'crypted_token': '3111d386531029ff9136510fc251d9033b550c1d',
        'token_hint': 'xkC8V',
        'crypted_refresh_token': 'ba5e2220d075de974ff42152d453e95a115c29ee',
    },
    'course-student': {
        'cleartext': 'T7J3DQMJzamkcPVWtkRh6zczx7CHEBy3JGJkvEeavcQyVKDGL9MAkveyJyDuAUEL',
        'crypted_token': '27516d47fc66ddd881621b798fb1b2ef097317ba',
        'token_hint': 'T7J3D',
        'crypted_refresh_token': '38ac483969e03a1075ed4297a832934087942b55',
    },
    'server-admin': {
        'cleartext': 'hHKUya4aDV6BnPDuDv8rL7TBFmxmGuBzTMFRrmFfDNaZM4Wy7WQKfufNt9kW9m3W',
        'crypted_token': '26d754ff6aa598e26905c872fbf3e4ca7ccfa5bd',
        'token_hint': 'hHKUy',
        'crypted_refresh_token': 'fb894a43938a8c4ab4c62c8fca4d4673f455b184',
    },
    'server-creator': {
        'cleartext': 'R9Z9GhYLrUArnc2cTAeu3Q7fkBhw7CZtuKB8A9eTVhvHWFKWrDVD769GnNzraAGJ',
        'crypted_token': '9aead9f139ba85c65d8e3a4a16e7e3561b8fc1c6',
        'token_hint': 'R9Z9G',
        'crypted_refresh_token': 'fba3fa43644182491f50fd92cecbb8dac8e70ef0',
    },
    'server-owner': {
        'cleartext': 'ycY4AhQ8ZGwk7L38vGur9HtG2WXevMcRh62eXU8KAfGRuXaXhXZE2wCthWVzRZn2',
        'crypted_token': '9d94301623bf938a1353e81d61571ff72064b2c9',
        'token_hint': 'ycY4A',
        'crypted_refresh_token': 'f793f9143aab179c7743a222bd39643f095cbf08',
    },
    'server-user': {
        'cleartext': 'vYNF6mWfcz4mQYBG6XJXeJh8x4WNNeQHkEkVDWAQxc8JBC9GJFwCffP9fznK4QMK',
        'crypted_token': '72b1dc493fcb142a7358bb4b86aa514ab57934fa',
        'token_hint': 'vYNF6',
        'crypted_refresh_token': '09f8920925ff204d43cbe6bce0bf07b6cc9ff465',
    },
}

# See: https://developerdocs.instructure.com/services/canvas/resources/enrollments#enrollment
COURSE_ROLE_ENROLLMENT_MAP = {
    'other': 'ObserverEnrollment',
    'student': 'StudentEnrollment',
    'grader': 'TaEnrollment',
    'admin': 'TaEnrollment',
    'owner': 'TeacherEnrollment',
}

# See: https://developerdocs.instructure.com/services/canvas/resources/assignments#assignment
ASSIGNMENT_SUBMISSION_TYPE_MAP = {
    'autograder': 'none',
}

# Convert a timestamp to a Canvas DateTime string.
# Timestamps are msecs since Unix epoch.
# Note that this may be different before Python 3.10,
# but the image will always have >= 3.10.
def timestamp_to_canvas(timestamp, timezone = datetime.timezone.utc):
    pytime = datetime.datetime.fromtimestamp(timestamp / 1000, timezone)
    return pytime.isoformat(timespec = 'milliseconds')

def run_sql(sql, db = 'canvas_development', clean_space = True):
    if (clean_space):
        sql = re.sub(r'\s+', ' ', sql)

    subprocess.run(f'psql -c "{sql}" {db}', shell = True, check = True)

def get_default_headers(user):
    token = user.get('canvas', {}).get('api_token', None)
    if (token is None):
        raise ValueError(f"User '{user['name']}' does not yet have an API token.")

    return {
        "Authorization": "Bearer %s" % (token),
        "Accept": "application/json+canvas-string-ids",
    }

def make_canvas_get(user, endpoint, **kwargs):
    return make_canvas_request(user, endpoint, requests_function = requests.get, **kwargs)

def make_canvas_post(user, endpoint, **kwargs):
    return make_canvas_request(user, endpoint, requests_function = requests.post, **kwargs)

def make_canvas_put(user, endpoint, **kwargs):
    return make_canvas_request(user, endpoint, requests_function = requests.put, **kwargs)

def make_canvas_request(user, endpoint,
        data = None, headers = None, json_body = True,
        requests_function = requests.post,
        api = True, default_heaaders = True):
    if (data is None):
        data = {}

    if (headers is None):
        headers = {}

    # Add in standard headers.
    if (default_heaaders):
        for (key, value) in get_default_headers(user).items():
            if (key not in headers):
                headers[key] = value

    if (api):
        endpoint = f"{API_BASE}/{endpoint}"

    url = f"{SERVER}/{endpoint}"

    response = requests_function(url, headers = headers, data = data)
    response.raise_for_status()

    body = None
    if (json_body):
        body = response.json()
    else:
        body = response.text

    return response, body

# Add users to canvas and add a 'canvas' dict to users that has 'account_id' and 'user_id'.
def add_users(users):
    for user in users.values():
        name = user['name']
        email = user['email']

        # The server owner is inserted on initial database population.
        if (name == 'server-owner'):
            continue

        # First, create an account for the user, with the site admin as the parent.
        data = {
            'account[name]': name,
            'account[sis_account_id]': email,
        }

        _, response_data = make_canvas_post(users['server-owner'], f"accounts/{SERVER_OWNER_ACCOUNT_ID}/sub_accounts", data = data)
        account_id = response_data['id']

        # Create a user for the new account.
        data = {
            'user[name]': name,
            'user[short_name]': name,
            'user[sortable_name]': name,
            'user[terms_of_use]': True,
            'user[skip_registration]': True,
            'pseudonym[unique_id]': email,
            'pseudonym[password]': name,
            'pseudonym[sis_user_id]': email,
            'pseudonym[integration_id]': email,
            'pseudonym[send_confirmation]': False,
            'pseudonym[force_self_registration]': False,
            'force_validations': False,
        }

        _, response_data = make_canvas_post(users['server-owner'], f"accounts/{account_id}/users", data = data)
        user_id = response_data['id']

        # Store the canvas info.
        user['canvas'] = {
            'account_id': account_id,
            'user_id': user_id,
        }

# Add courses (not erollments) to canvas and add a 'canvas' dict to courses that has 'course_id'.
def add_courses(users, courses):
    account_id = users['course-owner']['canvas']['account_id']

    for course in courses.values():
        data = {
            'course[name]': course['name'],
            'course[course_code]': course['id'],
            'course[is_public]': False,
            'course[is_public_to_auth_users]': False,
            'course[public_syllabus]': False,
            'course[public_syllabus_to_auth]': False,
            'course[allow_student_wiki_edits]': False,
            'course[allow_wiki_comments]': False,
            'course[allow_student_forum_attachments]': False,
            'course[open_enrollment]': False,
            'course[self_enrollment]': False,
            'offer': True,
            'enroll_me': False,
            'skip_course_template': True,
        }

        _, response_data = make_canvas_post(users['server-owner'], f"accounts/{account_id}/courses", data = data)
        course_id = response_data['id']

        course['canvas'] = {'course_id': course_id}

def add_enrollments(users, courses):
    for user in users.values():
        for (course_id, enrollment_info) in user.get('course-info', {}).items():
            role = enrollment_info['role']

            data = {
                'enrollment[user_id]': user['canvas']['user_id'],
                'enrollment[type]': COURSE_ROLE_ENROLLMENT_MAP[role],
                'enrollment[enrollment_state]': 'active',
                'enrollment[limit_privileges_to_course_section]': False,
                'enrollment[notify]': False,
            }

            canvas_course_id = courses[course_id]['canvas']['course_id']
            make_canvas_post(users['server-owner'], f"courses/{canvas_course_id}/enrollments", data = data)

# Add assignments to courses and add a 'canvas' dict to assignments that has 'assignment_id'.
def add_assignments(users, assignments, courses):
    for (course_id, course_assignments) in assignments.items():
        for assignment in course_assignments.values():
            data = {
                'assignment[name]': assignment['name'],
                'assignment[submission_types][]': ASSIGNMENT_SUBMISSION_TYPE_MAP[assignment['type']],
                'assignment[turnitin_enabled]': False,
                'assignment[vericite_enabled]': False,
                'assignment[peer_reviews]': False,
                'assignment[automatic_peer_reviews]': False,
                'assignment[notify_of_update]': False,
                'assignment[points_possible]': assignment['max-points'],
                'assignment[allowed_attempts]': -1,
                'assignment[grading_type]': 'points',
                'assignment[only_visible_to_overrides]': False,
                'assignment[published]': True,
                'assignment[quiz_lti]': False,
                'assignment[moderated_grading]': False,
                'assignment[omit_from_final_grade]': False,
                # For some reason, hide_in_gradebook gives a 400.
                # 'assignment[hide_in_gradebook]': False,
            }

            canvas_course_id = courses[course_id]['canvas']['course_id']
            _, response_data = make_canvas_post(users['server-owner'], f"courses/{canvas_course_id}/assignments", data = data)
            canvas_assignment_id = response_data['id']

            assignment['canvas'] = {'assignment_id': canvas_assignment_id}

def add_submissions(users, courses, assignments, submissions):
    for submission in submissions:
        canvas_course_id = courses[submission['course-id']]['canvas']['course_id']
        canvas_assignment_id = assignments[submission['course-id']][submission['assignment-id']]['canvas']['assignment_id']
        canvas_user_id = users[submission['user'].split('@')[0]]['canvas']['user_id']

        data = {
            'submission[posted_grade]': submission['score'],
            'submission[submitted_at]': timestamp_to_canvas(submission['grading-start-time']),
            'comment[text_comment]': submission['id'],
            'include[visibility]': True,
        }

        make_canvas_put(users['course-owner'], f"courses/{canvas_course_id}/assignments/{canvas_assignment_id}/submissions/{canvas_user_id}", data = data)

        # Canvas does not allow many dates to be set, so we have to manually set them in the DB.
        sql = f"""
            UPDATE public.submissions
            SET
                submitted_at = TO_TIMESTAMP({submission['grading-start-time'] / 1000}),
                graded_at = TO_TIMESTAMP({submission['grading-end-time'] / 1000}),
                posted_at = TO_TIMESTAMP({submission['grading-end-time'] / 1000})
            WHERE
                user_id = {canvas_user_id}
                AND assignment_id = {canvas_assignment_id}
                AND updated_at = (SELECT MAX(updated_at) FROM public.submissions)
            ;
        """

        run_sql(sql)

# Log in using the web interface and create an API token.
# An 'api_token' field will be added to the user's 'canvas' dict.
def create_api_token(user):
    session = requests.Session()

    # Go to the login page to set initial cookies.
    response = session.get(f"{SERVER}/login/canvas")
    response.raise_for_status()

    csrf_token = _parse_csrf_token(response)

    # Login

    data = {
        'utf8': '✓',
        'authenticity_token': csrf_token,
        'redirect_to_ssl': '1',
        'pseudonym_session[unique_id]': user['email'],
        'pseudonym_session[password]': user['password'],
        'pseudonym_session[remember_me]': '0',
    }

    response = session.post(f"{SERVER}/login/canvas", data = data)
    response.raise_for_status()

    # Create a token.

    csrf_token = _parse_csrf_token(response)

    data = {
        'token[purpose]': 'Initial API Token',
    }

    headers = {
        'x-csrf-token': csrf_token,
    }

    response = session.post(f"{SERVER}/api/v1/users/self/tokens", data = data, headers = headers)
    response.raise_for_status()

    data = response.json()

    api_token = data['visible_token']
    user['canvas']['api_token'] = api_token

def _parse_csrf_token(response):
    cookie = response.headers.get('set-cookie', None)
    if (cookie is None):
        raise ValueError('Failed to fetch cookie.')

    for item in cookie.split('; '):
        if (not item.startswith('_csrf_token')):
            continue

        token = item.replace('_csrf_token=', '')
        token = urllib.parse.unquote(token)
        return token

    raise ValueError("Unable to get login csrf token.")

# Load the data from disk into a dict, and arrange the data in dicts keyed as follows:
# - users: dict keyed by name,
# - courses: dict keyed by id,
# - assignments: dict keyed by course id then assignment id,
# - submissions: list.
def load_test_data():
    with open(USERS_FILE, 'r') as file:
        raw_users = json.load(file)

    with open(COURSES_FILE, 'r') as file:
        raw_courses = json.load(file)

    with open(ASSIGNMENTS_FILE, 'r') as file:
        raw_assignments = json.load(file)

    with open(SUBMISSIONS_FILE, 'r') as file:
        submissions = json.load(file)

    # Transform the data from a list into a dict.

    users = {user['name']: user for user in raw_users}
    courses = {course['id']: course for course in raw_courses}

    assignments = {}
    for (course_id, course_assignments) in raw_assignments.items():
        assignments[course_id] = {course_assignment['id']: course_assignment for course_assignment in course_assignments}

    return users, courses, assignments, submissions

# Replace users' existing tokens with static ones.
def replace_tokens(users):
    for (name, user) in users.items():
        token_info = STATIC_TOKENS.get(name, None)
        if (token_info is None):
            raise ValueError(f"Unable to find static token for '{name}'.")

        sql = f"""
            UPDATE public.access_tokens
            SET
                crypted_token = '{token_info['crypted_token']}',
                token_hint = '{token_info['token_hint']}',
                crypted_refresh_token = '{token_info['crypted_refresh_token']}'
            WHERE
                user_id = {user['canvas']['user_id']}
            ;
        """

        run_sql(sql)

# wait for the server to respond.
def wait_for_server():
    for _ in range(START_WAIT_ATTEMPTS):
        try:
            response = requests.get(SERVER)
            if (response.status_code == http.HTTPStatus.OK):
                return

            print(f"Server at startup responded with '{response.status_code}', waiting.")
        except requests.exceptions.ConnectionError as ex:
            print(f"Failed to connect to server at startup, waiting. Error: '{ex}'.")

        time.sleep(START_WAIT_TIME_SECS)

    raise ValueError(f"Server has not responded properly at startup after {START_WAIT_ATTEMPTS} tries.")

def main():
    users, courses, assignments, submissions = load_test_data()

    wait_for_server()
    print("Server is ready for data loading.")

    # Add in the server owner's info manually.
    # This is done for other users in add_users() (when they are created).
    users['server-owner']['canvas'] = {
        'account_id': SERVER_OWNER_ACCOUNT_ID,
        'user_id': SERVER_OWNER_USER_ID,
    }

    # Create an API token for server-owner.
    create_api_token(users['server-owner'])

    # Add the users.
    add_users(users)

    # Create tokens for all other users.
    for name, user in users.items():
        if (name != 'server-owner'):
            create_api_token(user)

    # Add the non-user information.
    add_courses(users, courses)
    add_enrollments(users, courses)
    add_assignments(users, assignments, courses)
    add_submissions(users, courses, assignments, submissions)

    # Replace the created tokens with static values.
    replace_tokens(users)

    return 0

if __name__ == '__main__':
    sys.exit(main())
