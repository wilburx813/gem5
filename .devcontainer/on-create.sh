#!/bin/bash

# Copyright (c) 2024 The Regents of the University of California
# All Rights Reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This script is run when the Docker container specified in devcontainer.json
# is created.

set -e

# Making the downloaded repository safe as the owner might differ for .devcontainer env.
git config --global --add safe.directory /workspaces/gem5

# Refresh the git index.
git update-index

# Install the pre-commit checks.
./util/pre-commit-install.sh

url="https://github.com/wilburx813/gem5/releases/download/0.1/prebuilt-gem5-X86.tar.gz"
tgz="prebuilt-gem5-X86.tar.gz"

if [ ! -f "$tgz" ]; then
    if command -v wget >/dev/null 2>&1; then
        wget -q "$url"
    elif command -v curl >/dev/null 2>&1; then
        curl -sSL -O "$url"
    else
        echo "Neither wget nor curl found; skipping download" >&2
    fi
fi

if [ -f "$tgz" ]; then
    tar -xzf "$tgz"
fi
