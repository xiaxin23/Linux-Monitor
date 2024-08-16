#基础镜像
FROM  ubuntu:18.04    

#从哪里获取用户输入，此处选择不交互
ARG DEBIAN_FRONTEND=noninteractive 
#环境变量，时区设置
ENV TZ=Asia/Shanghai

#声明使用终端
SHELL ["/bin/bash", "-c"]

# 执行部分清楚命令
RUN apt-get clean && \
    apt-get autoclean
COPY apt/sources.list /etc/apt/

#开始更新安装，在容器内安装
#基础软件包
RUN apt-get update  && apt-get upgrade -y  && \
    apt-get install -y \
    htop \
    apt-utils \
    curl \
    cmake \     
    git \
    openssh-server \
    build-essential \
    qtbase5-dev \
    qtchooser \
    qt5-qmake \
    qtbase5-dev-tools \
    libboost-all-dev \
    net-tools \
    vim \
    stress 


    #grpc需要的软件包
RUN apt-get install -y libc-ares-dev  libssl-dev gcc g++ make 

#QT所需的软件包
RUN apt-get install -y  \
    libx11-xcb1 \
    libfreetype6 \
    libdbus-1-3 \
    libfontconfig1 \
    libxkbcommon0   \
    libxkbcommon-x11-0


RUN apt-get install -y python-dev \
    python3-dev \
    python-pip \
    python-all-dev 

#COPY 在dockerfile中：当前目录下的内容转移到指定的位置
#构建的过程需要按照一定的顺序，其构建有着一定的依赖关系
COPY install/protobuf /tmp/install/protobuf
RUN /tmp/install/protobuf/install_protobuf.sh

COPY install/abseil /tmp/install/abseil
RUN /tmp/install/abseil/install_abseil.sh

COPY install/grpc /tmp/install/grpc
RUN /tmp/install/grpc/install_grpc.sh

# COPY install/cmake /tmp/install/cmake
# RUN /tmp/install/cmake/install_cmake.sh

# RUN apt-get install -y python3-pip
# RUN pip3 install cuteci -i https://mirrors.aliyun.com/pypi/simple

# COPY install/qt /tmp/install/qt
# RUN /tmp/install/qt/install_qt.sh






