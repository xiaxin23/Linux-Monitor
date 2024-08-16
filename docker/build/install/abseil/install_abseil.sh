#!/usr/bin/env bash

#报错相关
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"

# https://github.com/abseil/abseil-cpp/archive/refs/tags/20200225.2.tar.gz
# Install abseil.
#内核数 单CPU
THREAD_NUM=$(nproc)  

# PKG_NAME表示此包的名字
VERSION="20200225.2"
PKG_NAME="abseil-cpp-${VERSION}.tar.gz"

tar xzf "${PKG_NAME}"    
pushd "abseil-cpp-${VERSION}"
    mkdir build && cd build
    cmake .. \
        -DBUILD_SHARED_LIBS=ON \
        -DCMAKE_CXX_STANDARD=14 \
        -DCMAKE_INSTALL_PREFIX=/usr/local
    make -j${THREAD_NUM}  #使用最大核数进行编译
    make install
popd #退出

#动态链接库管理
ldconfig

# Clean up
rm -rf "abseil-cpp-${VERSION}" "${PKG_NAME}"