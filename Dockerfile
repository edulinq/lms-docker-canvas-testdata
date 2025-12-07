FROM ghcr.io/edulinq/lms-docker-canvas-base:0.0.5

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /work

# Install Python Dependencies
COPY ./requirements.txt /work/
RUN pip3 install -r /work/requirements.txt

WORKDIR /work/canvas-source

# Copy Scripts and Data
COPY ./lms-testdata /work/lms-testdata
COPY ./scripts/load-data.py /work/scripts/

# Populate with test data.
RUN \
    # Start DB \
    service postgresql start \
    # Start Server \
    && bundle exec rails server -d \
    # Start background job processor. \
    && bundle exec script/delayed_job start \
    # Sleep for short time to let the server start. \
    && echo "Waiting for server to start." \
    && sleep 5 \
    # Load the data, cat the log on failure. \
    && echo "Loading data." \
    && (python3 /work/scripts/load-data.py \
        || ( \
            echo "--------------- CANVAS LOG ---------------" \
            && cat /work/canvas-source/log/development.log \
            && echo "--------------- DATABASE LOG ---------------" \
            && cat /var/log/postgresql/postgresql-14-main.log \
            && echo "------------------------------------------" \
            && false \
        ) \
    ) \
    # Sleep for short time to let background jobs finish. \
    && echo "Waiting for background jobs." \
    && sleep 5 \
    # Stop background jobs. \
    && bundle exec script/delayed_job stop \
    # Stop Server \
    && pgrep -f puma | xargs kill \
    # Remove the sevrer's PID file. \
    && rm -rf /work/canvas-source/tmp \
    # Stop DB \
    && service postgresql stop
