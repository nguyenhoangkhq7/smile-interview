# Backend

## Database

`src/main/resources/db/migration/V1__init_schema.sql` is the initial schema for
the current pipeline. It creates six application tables and the existing
development ADMIN/HR accounts. PostgreSQL 17 is supported without extensions.

CV and JD text is stored only in `raw_text`. Upload endpoints also accept the
legacy input names `parsed_content` and `extracted_text`, and store their values
in `raw_text`.

The previous V1–V17 history has been replaced before deployment. Start with an
empty development database when using this revision; an existing database with
the old Flyway history cannot be upgraded with this V1. Changing migration files
does not reset an existing database or Docker volume.

## Verification

With Java 21+ and an empty test PostgreSQL database, set
`SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, and
`SPRING_DATASOURCE_PASSWORD`, then run `./mvnw test` (`mvnw.cmd test` on Windows).
The tests run Flyway, validate Hibernate mappings, and check persistence and
foreign-key cleanup for the current pipeline. Use a separate test database:
Flyway creates its schema and development accounts during application startup.
