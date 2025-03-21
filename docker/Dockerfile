ARG UBUNTU_VERSION=20.04
FROM ubuntu:${UBUNTU_VERSION}

USER root

ARG TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ >/etc/timezone

ARG DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/bin:${PATH}"

### update apt repo
RUN apt-get update && apt-get install -y \
    software-properties-common && \
    add-apt-repository universe && \
    add-apt-repository multiverse && \
    apt-get update

### install utils
RUN apt-get update && apt-get install -y \
        git vim sudo \
        libva-dev \
        pciutils \
        kmod

# X11 forwarding and xcb
RUN apt-get install -y x11-apps libx11-6 xauth libxext6 libxrender1 libxtst6 libxi6 libxcb-xinerama0

WORKDIR /deepx

ADD archives/dx_rt.tar.gz /deepx/dx_rt/
RUN cd /deepx/dx_rt && \
    ./install.sh --dep && \
    ./build.sh --install

ADD archives/dx_app.tar.gz /deepx/dx_app/
RUN cd /deepx/dx_app && \
    ./install.sh --all && \
    ./build.sh

ADD archives/dx_stream.tar.gz /deepx/dx_stream/
RUN cd /deepx/dx_stream && \
    ./install.sh && \
    ./build.sh --install

RUN rm -rf /deepx/dx_stream/util && \
    rm -rf /deepx/dx_app/util && \
    rm -rf /deepx/dx_app/build_x86_64 && \
    rm -rf /deepx/dx_rt/build_x86_64

RUN apt-get update && \
    apt-get install -y \
    vim fim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/local/bin/dxrtd" ]
