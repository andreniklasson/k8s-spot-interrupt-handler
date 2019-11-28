FROM alpine:3.6

ARG KUBE_VERSION=1.15.0
ENV HOME=/srv
WORKDIR /srv

RUN apk add --no-cache curl ca-certificates
RUN curl -f -s -o /usr/local/bin/kubectl https://storage.googleapis.com/kubernetes-release/release/v${KUBE_VERSION}/bin/linux/amd64/kubectl && \
    chmod +x /usr/local/bin/kubectl && \
    kubectl version --client

COPY spot-interrupt-handler.py .

RUN chmod +x spot-interrupt-handler.py

ENV PYTHONUNBUFFERED=1

RUN echo "**** install Python ****" && \
    apk add --no-cache python3 && \
    if [ ! -e /usr/bin/python ]; then ln -sf python3 /usr/bin/python ; fi && \
    \
    echo "**** install pip ****" && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --no-cache --upgrade pip setuptools wheel && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi

RUN pip3 install boto3
RUN pip3 install requests

CMD [ "python3", "spot-interrupt-handler.py" ]