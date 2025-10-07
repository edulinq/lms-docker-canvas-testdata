FROM ghcr.io/edulinq/lms-docker-canvas-base:0.0.3

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /work

# Install Python Dependencies
COPY ./requirements.txt /work/
RUN pip3 install -r /work/requirements.txt

WORKDIR /work/canvas-source

# Copy Scripts and Data
COPY ./testdata/raw /work/data
COPY ./scripts/load-data.py /work/scripts/

# Populate with test data.
RUN \
    # Start DB \
    service postgresql start \
    # Start Server \
    && bundle exec rails server -d \
    # Sleep for short time to let the server start. \
    && sleep 5 \
    # Load the data, cat the log on failure. \
    && (python3 /work/scripts/load-data.py || (echo "---------------" && cat /work/canvas-source/log/development.log && false)) \
    # Stop Server \
    && pgrep -f puma | xargs kill \
    # Stop DB \
    && service postgresql stop

ENTRYPOINT ["/work/scripts/entrypoint.sh"]
