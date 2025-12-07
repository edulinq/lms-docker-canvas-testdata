#!/usr/bin/env python3

import datetime
import http
import os
import urllib.parse
import re
import subprocess
import sys
import time

import edq.util.pyimport
import requests

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(THIS_DIR, '..', 'lms-testdata', 'testdata')
LOAD_SCRIPT = os.path.join(THIS_DIR, '..', 'lms-testdata', 'load.py')

SERVER = 'http://127.0.0.1:3000'
API_BASE = 'api/v1'

# On update, Canvas will not always wait for the operation to complete to return.
# We need to sleep to ensure consistent IDs.
API_WRITE_WAIT_SECS = 0.10

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
ASSIGNMENT_SUBMISSION_TYPE_NONE = 'none'
ASSIGNMENT_SUBMISSION_TYPE_MAP = {
    'autograder': ASSIGNMENT_SUBMISSION_TYPE_NONE,
}

# Convert a timestamp to a Canvas DateTime string.
# Timestamps are msecs since Unix epoch.
# Note that this may be different before Python 3.10,
# but the image will always have >= 3.10.
def timestamp_to_canvas(timestamp, timezone = datetime.timezone.utc):
    pytime = datetime.datetime.fromtimestamp(timestamp / 1000, timezone)
    return pytime.isoformat(timespec = 'milliseconds')

def run_sql(sql, db = 'canvas_development', clean_space = True, check = True, get_records = False):
    if (clean_space):
        sql = re.sub(r'\s+', ' ', sql)

    if (not get_records):
        subprocess.run(f'psql -c "{sql}" {db}', shell = True, check = check)
        return None

    results = subprocess.run(f'psql --no-align --quiet --tuples-only -c "{sql}" {db}', shell = True, check = check, capture_output = True)
    return results.stdout.decode('utf-8').splitlines()

def get_default_headers(user):
    token = user.get('canvas_api_token', None)
    if (token is None):
        raise ValueError(f"User '{user['name']}' does not yet have an API token.")

    return {
        "Authorization": "Bearer %s" % (token),
        "Accept": "application/json+canvas-string-ids",
    }

def make_canvas_get(user, endpoint, **kwargs):
    return make_canvas_request(user, endpoint, requests_function = requests.get, **kwargs)

def make_canvas_post(user, endpoint, **kwargs):
    response = make_canvas_request(user, endpoint, requests_function = requests.post, **kwargs)
    time.sleep(API_WRITE_WAIT_SECS)
    return response

def make_canvas_put(user, endpoint, **kwargs):
    response = make_canvas_request(user, endpoint, requests_function = requests.put, **kwargs)
    time.sleep(API_WRITE_WAIT_SECS)
    return response

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
        user['canvas_account_id'] = response_data['id']

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

        _, response_data = make_canvas_post(users['server-owner'], f"accounts/{user['canvas_account_id']}/users", data = data)
        canvas_user_id = response_data['id']

        # Update the canvas ID to match ours.
        _update_user_id(canvas_user_id, user['id'])

def _delete_auditing_records(auditing_record_type):
    # Canvas is annoying and makes table names based on the current date, so we have to fetch the table names.
    sql = f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE
            table_schema = 'public'
            AND table_name LIKE 'auditor_{auditing_record_type}_records%'
        ;
    """
    auditing_tables = run_sql(sql, get_records = True)

    for auditing_table in auditing_tables:
        run_sql(f"DELETE FROM {auditing_table};")

def _update_user_id(old_id, new_id):
    _delete_auditing_records('authentication')

    sql = f"""
        WITH
        access_tokens_fk_update_fk_update as (
            UPDATE public.access_tokens
            SET user_id = {new_id}
            WHERE user_id = {old_id}
        ),
        account_users_fk_update as (
            UPDATE public.account_users
            SET user_id = {new_id}
            WHERE user_id = {old_id}
        ),
        communication_channels_fk_update as (
            UPDATE public.communication_channels
            SET user_id = {new_id}
            WHERE user_id = {old_id}
        ),
        pseudonyms_channels_fk_update as (
            UPDATE public.pseudonyms
            SET user_id = {new_id}
            WHERE user_id = {old_id}
        ),
        user_account_associations_channels_fk_update as (
            UPDATE public.user_account_associations
            SET user_id = {new_id}
            WHERE user_id = {old_id}
        )
        UPDATE public.users
        SET id = {new_id}
        WHERE id = {old_id}
        ;
    """
    run_sql(sql)

def add_courses(users, courses):
    account_id = users['server-owner']['canvas_account_id']

    for course in courses.values():
        data = {
            'course[name]': course['name'],
            'course[course_code]': course['short-name'],
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

        syllabus = course.get('syllabus', None)
        if (syllabus is not None):
            data['course[syllabus_body]'] = syllabus

        _, response_data = make_canvas_post(users['server-owner'], f"accounts/{account_id}/courses", data = data)
        canvas_course_id = response_data['id']

        # Update ID.

        _delete_auditing_records('course')

        sql = f"""
            WITH
                course_account_associations_fk_update AS (
                    UPDATE public.course_account_associations
                    SET course_id = {course['id']}
                    WHERE course_id = {canvas_course_id}
                ),
                post_policies_fk_update AS (
                    UPDATE public.post_policies
                    SET course_id = {course['id']}
                    WHERE course_id = {canvas_course_id}
                )
            UPDATE public.courses
            SET id = {course['id']}
            WHERE id = {canvas_course_id}
            ;
        """
        run_sql(sql)

def add_enrollments(users, courses):
    for user in users.values():
        for (course_name, enrollment_info) in user.get('course-info', {}).items():
            role = enrollment_info['role']

            data = {
                'enrollment[user_id]': user['id'],
                'enrollment[type]': COURSE_ROLE_ENROLLMENT_MAP[role],
                'enrollment[enrollment_state]': 'active',
                'enrollment[limit_privileges_to_course_section]': False,
                'enrollment[notify]': False,
            }

            make_canvas_post(users['server-owner'], f"courses/{courses[course_name]['id']}/enrollments", data = data)

def add_assignments(users, assignments, courses):
    for assignment in assignments.values():
        course_name = assignment['course']

        data = {
            'assignment[name]': assignment['name'],
            'assignment[submission_types][]': ASSIGNMENT_SUBMISSION_TYPE_MAP.get(assignment.get('type', None), ASSIGNMENT_SUBMISSION_TYPE_NONE),
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

        _, response_data = make_canvas_post(users['server-owner'], f"courses/{courses[course_name]['id']}/assignments", data = data)
        canvas_assignment_id = response_data['id']

        # Update ID.

        sql = f"""
            WITH
                post_policies_fk_update AS (
                    UPDATE public.post_policies
                    SET assignment_id = {assignment['id']}
                    WHERE assignment_id = {canvas_assignment_id}
                ),

                submissions_fk_update AS (
                    UPDATE public.submissions
                    SET assignment_id = {assignment['id']}
                    WHERE assignment_id = {canvas_assignment_id}
                )
            UPDATE public.assignments
            SET id = {assignment['id']}
            WHERE id = {canvas_assignment_id}
            ;
        """
        run_sql(sql)

def add_submissions(users, courses, assignments, submissions):
    for submission in submissions.values():
        canvas_course_id = courses[submission['course']]['id']
        canvas_assignment_id = assignments[submission['assignment']]['id']
        user_id = users[submission['user']]['id']

        data = {
            'submission[posted_grade]': submission['score'],
            'include[visibility]': True,
        }

        make_canvas_put(users['server-owner'], f"courses/{canvas_course_id}/assignments/{canvas_assignment_id}/submissions/{user_id}", data = data)

        _delete_auditing_records('grade_change')

        # Canvas does not allow all the values we need to be set, so manually set them in the DB along with the ID.
        set_values = {'id': submission['id']}

        # Canvas does not allow many dates to be set, so we have to manually set them in the DB.
        grading_start_time = submission.get('grading-start-time', None)
        grading_end_time = submission.get('grading-end-time', None)

        if (grading_start_time is not None):
            set_values['submitted_at'] = f"TO_TIMESTAMP({grading_start_time / 1000})"

        if (grading_end_time is not None):
            set_values['graded_at'] = f"TO_TIMESTAMP({grading_end_time / 1000})"
            set_values['posted_at'] = f"TO_TIMESTAMP({grading_end_time / 1000})"

        set_sql = ', '.join([f"{field} = {value}" for (field, value) in set_values.items()])

        sql = f"""
            UPDATE public.submissions
            SET {set_sql}
            WHERE
                assignment_id = {canvas_assignment_id}
                AND user_id = {user_id}
            ;
        """

        run_sql(sql)

def add_groups(users, courses, assignments, groupsets):
    for groupset in groupsets.values():
        canvas_course_id = courses[groupset['course']]['id']
        canvas_assignment_id = assignments[groupset['assignment']]['id']

        data = {
            'name': groupset['name'],
            'create_group_count': 0,
        }

        _, response_data = make_canvas_post(users['course-owner'], f"courses/{canvas_course_id}/group_categories", data = data)
        temp_canvas_groupset_id = response_data['id']

        sql = f"""
            UPDATE public.group_categories
            SET id = {groupset['id']}
            WHERE id = {temp_canvas_groupset_id}
            ;
        """
        run_sql(sql)

        for group in groupset['groups']:
            _add_group(users, group, groupset)

def _add_group(users, group, groupset):
    data = {
        'name': group['name'],
    }

    _, response_data = make_canvas_post(users['course-owner'], f"group_categories/{groupset['id']}/groups", data = data)
    temp_canvas_group_id = response_data['id']

    sql = f"""
        UPDATE public.groups
        SET id = {group['id']}
        WHERE id = {temp_canvas_group_id}
        ;
    """
    run_sql(sql)

    for user_name in group['users']:

        data = {
            'user_id': users[user_name]['id']
        }

        make_canvas_post(users['course-owner'], f"groups/{group['id']}/memberships", data = data)

# Log in using the web interface and create an API token.
# An 'canvas_api_token' field will be added to the user.
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

    user['canvas_api_token'] = data['visible_token']

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

# Replace users' existing tokens with static ones.
def replace_tokens(users):
    for (name, user) in users.items():
        token_info = STATIC_TOKENS.get(name, None)
        if (token_info is None):
            continue

        sql = f"""
            UPDATE public.access_tokens
            SET
                crypted_token = '{token_info['crypted_token']}',
                token_hint = '{token_info['token_hint']}',
                crypted_refresh_token = '{token_info['crypted_refresh_token']}'
            WHERE
                user_id = {user['id']}
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
    # The Python pathing makes it easier to load this dynamically.
    dataset = edq.util.pyimport.import_path(LOAD_SCRIPT).load_test_data(DATA_DIR)
    (users, courses, assignments, groupsets, submissions) = dataset

    wait_for_server()
    print("Server is ready for data loading.")

    # Add in the server owner's info manually.
    # This is done for other users in add_users() (when they are created).
    users['server-owner']['canvas_account_id'] = SERVER_OWNER_ACCOUNT_ID
    _update_user_id(SERVER_OWNER_USER_ID, users['server-owner']['id'])

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
    add_groups(users, courses, assignments, groupsets)

    # Replace the created tokens with static values.
    replace_tokens(users)

    return 0

if __name__ == '__main__':
    sys.exit(main())
