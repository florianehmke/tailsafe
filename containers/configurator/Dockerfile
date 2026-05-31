FROM registry.access.redhat.com/ubi9/python-312@sha256:2fe5123348908fbf17b5f3039a232f2616092997e698af2a214051b41792d37a

USER 0
RUN dnf install -y httpd-tools && dnf clean all

WORKDIR /app
COPY scripts /app/scripts
COPY containers/configurator/entrypoint.sh /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
