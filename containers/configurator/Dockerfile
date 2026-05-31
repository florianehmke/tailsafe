FROM registry.access.redhat.com/ubi9/python-312@sha256:52d1ffcda3b9552934f947b7d41fb0cb66973bdc0d7e91814facadc126f68663

USER 0
RUN dnf install -y httpd-tools && dnf clean all

WORKDIR /app
COPY scripts /app/scripts
COPY containers/configurator/entrypoint.sh /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
