# Builds the debug APK on a Linux machine (e.g. your home server) with no IDE.
# Output: ./out/app-debug.apk on the host.
#
#   DOCKER_BUILDKIT=1 docker build --target export --output ./out .
#
FROM eclipse-temurin:17-jdk AS build

ENV ANDROID_SDK_ROOT=/opt/android-sdk
# Android command-line tools build number; bump if the download 404s.
ENV CMDLINE_TOOLS_VERSION=11076708

RUN apt-get update && apt-get install -y --no-install-recommends unzip wget \
    && rm -rf /var/lib/apt/lists/*

# Android SDK (command-line tools + the platform/build-tools this project needs)
RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip -O /tmp/cmdtools.zip \
    && unzip -q /tmp/cmdtools.zip -d ${ANDROID_SDK_ROOT}/cmdline-tools \
    && mv ${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/latest \
    && rm /tmp/cmdtools.zip
ENV PATH=${PATH}:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools
RUN yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0" >/dev/null

WORKDIR /project
COPY . .
# The committed Gradle wrapper downloads the matching Gradle itself.
RUN chmod +x ./gradlew && ./gradlew assembleDebug --no-daemon

# Export stage: lets `--output` drop the APK straight onto the host.
FROM scratch AS export
COPY --from=build /project/app/build/outputs/apk/debug/app-debug.apk /app-debug.apk
