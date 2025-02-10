FROM ubuntu:20.04

USER root

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y sudo software-properties-common && \
    add-apt-repository universe && \
    add-apt-repository multiverse && \
    apt-get update

RUN apt-get install -y x11-apps libx11-6 xauth libxext6 libxrender1 libxtst6 libxi6

WORKDIR /app

ADD archives/dx_rt.tar.gz /app/dx_rt/
ADD archives/dx_app.tar.gz /app/dx_app/
ADD archives/dx_stream.tar.gz /app/dx_stream/

RUN cd /app/dx_rt && \
    ./install.sh --dep && \
    ./build.sh --install

RUN cd /app/dx_app && \
    ./install.sh --all && \
    ./build.sh

RUN cd /app/dx_stream && \
    ./install.sh && \
    ./build.sh --install

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

RUN rm -rf /app/dx_stream/util && \
    rm -rf /app/dx_app/util && \
    rm -rf /app/dx_app/build_x86_64 && \
    rm -rf /app/dx_rt/build_x86_64

ENTRYPOINT [ "/usr/local/bin/dxrtd" ]
