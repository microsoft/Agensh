# One-shot provisioning client for the profile's Gitea and Mattermost services.
FROM alpine:3.20

RUN apk add --no-cache bash curl jq git openssl

COPY bootstrap.sh /usr/local/bin/bootstrap.sh
RUN chmod +x /usr/local/bin/bootstrap.sh

ENTRYPOINT ["/usr/local/bin/bootstrap.sh"]
