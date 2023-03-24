FROM ubuntu:22.04
RUN apt-get update \
&& DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
  bison \
  build-essential \
  cargo \
  git \
  libssl-dev \
  pkg-config \
  python3 \
  python3-pip \
  repo \
  rsync \
  ssh \
  unzip \
  zip \
  # clang-3289846 uses host libncurses5
  libncurses5 \
  # Necessary to test 32-bit runtimes.
  gcc-multilib \
  libc6-dev-i386-cross \
&& rm -rf /var/lib/apt/lists/*

# Install TensorFlow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --require-hashes -r /tmp/requirements.txt \
&& rm -rf /root/.cache/pip /tmp/requirements.txt
ENV TENSORFLOW_INSTALL=/usr/local/lib/python3.10/dist-packages/tensorflow

# Install sccache
RUN cargo install --root /usr/local --no-default-features --features=gcs sccache \
&& rm -rf /root/.cargo

# Set up git user identity, as required by repo
RUN printf '[user]\n  name = Builder\n  email = android-llvm+kokoro@google.com' > /etc/gitconfig
