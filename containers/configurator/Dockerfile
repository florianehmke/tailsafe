FROM python:3.12-alpine

RUN apk add --no-cache apache2-utils

WORKDIR /app
COPY scripts /app/scripts
COPY containers/configurator/entrypoint.sh /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
