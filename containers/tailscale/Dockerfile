ARG TAILSCALE_VERSION=stable
FROM tailscale/tailscale:${TAILSCALE_VERSION}

COPY containers/tailscale/entrypoint.sh /usr/local/bin/tailsafe-tailscale
ENTRYPOINT ["/usr/local/bin/tailsafe-tailscale"]
