FROM debian:12-slim
SHELL ["/bin/bash", "-c"]

COPY entrypoint.sh /usr/src/entrypoint.sh
RUN chmod +xr /usr/src/entrypoint.sh

VOLUME /scanme
ENTRYPOINT ["/usr/src/entrypoint.sh"]

