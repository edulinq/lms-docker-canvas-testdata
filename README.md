# LMS Docker Image - Canvas With Test Data

A [Docker](https://en.wikipedia.org/wiki/Docker_(software)) image running an instance of
[Instructure's Canvas Learning Management System (LMS)](https://en.wikipedia.org/wiki/Instructure).
This image is based off of [ghcr.io/edulinq/lms-docker-canvas-base](https://github.com/edulinq/lms-docker-canvas-base),
and includes test data (users, courses, assignments, etc).

## Usage

The docker image is fairly standard, and does not require special care when building or running.

Running the scripts in this project requires Python >= 3.8 and the dependencies listed in [requirements.txt](requirements.txt).
You can install these requirements in pip with:
```sh
pip install -r requirements.txt -r requirements-dev.txt
```

### Building

You can build an image with the tag `lms-docker-canvas-testdata` using:
```sh
docker build -t lms-docker-canvas-testdata .
```

### Running

Once built, the container can be run using standard options.
Canvas uses port 3000 by default, so that port should be passed through:
```sh
# Using the previously built image.
docker run --rm -it -p 3000:3000 --name canvas lms-docker-canvas-testdata

# Using the pre-built image.
docker run --rm -it -p 3000:3000 --name canvas ghcr.io/edulinq/lms-docker-canvas-testdata
```

### Generating Test HTTP Data

To generate test HTTP data (for use in a [mock HTTP server](https://github.com/edulinq/python-utils/blob/main/edq/testing/httpserver.py)),
you can use the [scripts/generate-test-data.py](scripts/generate-test-data.py) script:
```sh
# Using the pre-built image.
./scripts/generate-test-data.py

# Using the previously built image.
./scripts/generate-test-data.py --image-name lms-docker-canvas-testdata
```

This will generate test HTTP exchanges in the [testdata/http](testdata/http) directory.

Use `--help` to see other available options (such as output directory).

### Verifying Test HTTP Data

To verify that test data matches the output of a Canvas image,
you can use the [scripts/verify-test-data.py](scripts/verify-test-data.py) script:
```sh
# Using the pre-built image.
./scripts/verify-test-data.py

# Using the previously built image.
./scripts/verify-test-data.py --image-name lms-docker-canvas-testdata
```

This will verify that the test HTTP exchanges in the [testdata/http](testdata/http) directory
get the same response from you Canvas image.

This verification step is also done as part of CI.

Use `--help` to see other available options (such as the test data directory).

## User Authentication

All created users have a password that is the same as their name.
In addition, all users modified to have static API tokens that are consistent between builds:

| Name / Password | Email                           | API Token                                                        |
|-----------------|---------------------------------|------------------------------------------------------------------|
| course-admin    | course-admin@test.edulinq.org   | nHRkQ39czXL2x7xxKrPYmvtYTyWJCCHCVRMZTfTfZtJZZWXHnkN9UhnCy37XuYeK |
| course-grader   | course-grader@test.edulinq.org  | uwRzuhDzDyEJBuJ8QR8PRTLAZHRU7ErY6aTtACNtB7tHZNVzLLw2AGZTGLQya9YX |
| course-other    | course-other@test.edulinq.org   | VntnXWUfHDYDGhFV8VPmUrMEVuwJ3JeJ898FFDf7DHkGJ7vmrEW3eJx9cuHukh94 |
| course-owner    | course-owner@test.edulinq.org   | xkC8V8BWX4RFx7JMYyZuyDvtDAKRxuGHRxTR268eHzXCPYU46vw89DrBADat4n6U |
| course-student  | course-student@test.edulinq.org | T7J3DQMJzamkcPVWtkRh6zczx7CHEBy3JGJkvEeavcQyVKDGL9MAkveyJyDuAUEL |
| server-admin    | server-admin@test.edulinq.org   | hHKUya4aDV6BnPDuDv8rL7TBFmxmGuBzTMFRrmFfDNaZM4Wy7WQKfufNt9kW9m3W |
| server-creator  | server-creator@test.edulinq.org | R9Z9GhYLrUArnc2cTAeu3Q7fkBhw7CZtuKB8A9eTVhvHWFKWrDVD769GnNzraAGJ |
| server-owner    | server-owner@test.edulinq.org   | ycY4AhQ8ZGwk7L38vGur9HtG2WXevMcRh62eXU8KAfGRuXaXhXZE2wCthWVzRZn2 |
| server-user     | server-user@test.edulinq.org    | vYNF6mWfcz4mQYBG6XJXeJh8x4WNNeQHkEkVDWAQxc8JBC9GJFwCffP9fznK4QMK |


## Licensing

This repository is provided under the MIT licence (see [LICENSE](./LICENSE)).
Canvas LMS is covered under the [AGPL-3.0 license](https://github.com/instructure/canvas-lms/blob/master/LICENSE).
