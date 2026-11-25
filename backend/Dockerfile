# Stage 1: Build stage
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /app

COPY --chmod=0755 mvnw .
COPY .mvn .mvn
COPY pom.xml .
COPY src src
RUN --mount=type=cache,target=/root/.m2,sharing=locked \
    ./mvnw -B -DskipTests package

# Stage 2: Runtime stage
FROM eclipse-temurin:21-jre
WORKDIR /app

RUN groupadd --system --gid 1001 appgroup \
 && useradd --system --uid 1001 --gid appgroup appuser \
 && mkdir -p /app/uploads/avatars \
 && chown -R appuser:appgroup /app

# Copy the built jar from the builder stage
COPY --from=builder --chown=appuser:appgroup /app/target/*.jar app.jar

USER appuser

EXPOSE 8081

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8081/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
