# Stage 1: Build stage
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /app

# Copy the Maven wrapper and pom.xml first to cache dependencies
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .

# Grant execute permission for the maven wrapper and download dependencies
RUN chmod +x mvnw
RUN ./mvnw dependency:go-offline -B

# Copy the source code and package the application
COPY src src
RUN ./mvnw clean package -DskipTests -B

# Stage 2: Runtime stage
FROM eclipse-temurin:21-jre
WORKDIR /app

# Copy the built jar from the builder stage
COPY --from=builder /app/target/*.jar app.jar

# Expose the default port
EXPOSE 8080

# Run the jar file
ENTRYPOINT ["java", "-jar", "app.jar"]
