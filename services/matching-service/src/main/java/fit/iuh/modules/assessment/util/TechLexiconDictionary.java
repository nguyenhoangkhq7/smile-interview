package fit.iuh.modules.assessment.util;

import java.util.*;

/**
 * Domain Lexicon Dictionary for IT & Software Engineering terminology,
 * acronyms, and aliases.
 *
 * <p>Provides bidirectional synonym mapping (e.g. k8s <-> kubernetes,
 * golang <-> go, postgres <-> postgresql, gcp <-> google cloud) to prevent
 * false-positive grounding penalties in {@link fit.iuh.modules.assessment.service.EvidenceGroundingValidator}
 * and enhance lexical matching across the matching engine.
 */
public final class TechLexiconDictionary {

    private TechLexiconDictionary() {
        throw new UnsupportedOperationException("Utility lexicon dictionary class");
    }

    private static final Map<String, Set<String>> SYNONYM_MAP = new HashMap<>();
    private static final Map<String, String> CANONICAL_MAP = new HashMap<>();

    static {
        // --- Programming Languages ---
        registerGroup("java", "jvm", "j2ee", "core java");
        registerGroup("golang", "go", "go-lang");
        registerGroup("python", "python3", "py");
        registerGroup("javascript", "js", "ecmascript", "es6", "es2015", "es2020");
        registerGroup("typescript", "ts");
        registerGroup("c++", "cpp", "c/c++");
        registerGroup("c#", "csharp", "c-sharp", ".net", "dotnet");
        registerGroup("php", "php7", "php8");
        registerGroup("rust", "rustlang");
        registerGroup("kotlin", "kotlin/jvm");
        registerGroup("swift", "swiftlang", "ios swift");
        registerGroup("ruby", "ruby on rails", "ror");
        registerGroup("dart", "flutter/dart");

        // --- Frontend Frameworks & Libraries ---
        registerGroup("react", "reactjs", "react.js", "react-native", "react native");
        registerGroup("vue", "vuejs", "vue.js", "vue3", "vue2");
        registerGroup("angular", "angularjs", "angular.js", "angular 2+");
        registerGroup("next.js", "nextjs", "next");
        registerGroup("nuxt.js", "nuxtjs", "nuxt");
        registerGroup("svelte", "sveltekit");
        registerGroup("tailwind", "tailwindcss", "tailwind-css");
        registerGroup("html", "html5");
        registerGroup("css", "css3", "scss", "sass");
        registerGroup("redux", "redux-toolkit", "rtk");

        // --- Backend Frameworks & APIs ---
        registerGroup("spring boot", "spring", "springboot", "spring-boot", "spring framework", "spring cloud");
        registerGroup("node.js", "nodejs", "node");
        registerGroup("express", "expressjs", "express.js");
        registerGroup("nestjs", "nest.js", "nest");
        registerGroup("fastapi", "fast api");
        registerGroup("django", "django rest framework", "drf");
        registerGroup("flask");
        registerGroup("asp.net", "asp.net core", ".net core", "dotnet core");
        registerGroup("laravel");
        registerGroup("gin", "gin-gonic");
        registerGroup("grpc", "g-rpc", "protocol buffers", "protobuf");
        registerGroup("graphql", "graph-ql", "apollo graphql");
        registerGroup("rest", "restful", "rest api", "rest apis", "restful api");

        // --- Databases, Caches & Message Brokers ---
        registerGroup("postgresql", "postgres", "psql", "pgsql");
        registerGroup("mysql", "my-sql");
        registerGroup("mongodb", "mongo", "mongo-db");
        registerGroup("redis", "redis cache");
        registerGroup("elasticsearch", "elastic search", "es", "elk", "elk stack");
        registerGroup("cassandra", "apache cassandra");
        registerGroup("oracle", "oracle db", "pl/sql", "plsql");
        registerGroup("sql server", "mssql", "ms sql", "microsoft sql server");
        registerGroup("sqlite", "sqlite3");
        registerGroup("dynamodb", "dynamo db");
        registerGroup("kafka", "apache kafka");
        registerGroup("rabbitmq", "rabbit mq", "amqp");

        // --- Cloud & DevOps ---
        registerGroup("kubernetes", "k8s", "k8-s", "kube");
        registerGroup("docker", "dockerfile", "docker compose", "docker-compose", "containerization");
        registerGroup("aws", "amazon web services", "amazon aws");
        registerGroup("google cloud", "gcp", "google cloud platform");
        registerGroup("azure", "microsoft azure", "ms azure");
        registerGroup("ci/cd", "ci-cd", "cicd", "continuous integration", "continuous deployment", "github actions", "gitlab ci", "jenkins");
        registerGroup("terraform", "tf", "iac", "infrastructure as code");
        registerGroup("ansible");
        registerGroup("linux", "ubuntu", "debian", "centos", "rhel", "alpine");
        registerGroup("nginx");

        // --- Testing & QA ---
        registerGroup("unit test", "unit testing", "unittests", "tdd", "test driven development");
        registerGroup("junit", "junit5", "junit4");
        registerGroup("mockito");
        registerGroup("selenium", "selenium webdriver");
        registerGroup("cypress", "cypress.io");
        registerGroup("jest", "jestjs");
        registerGroup("playwright");
        registerGroup("postman");
        registerGroup("jmeter", "apache jmeter");

        // --- Architecture & Concepts ---
        registerGroup("microservices", "microservice", "micro-services", "micro-service", "distributed systems");
        registerGroup("oop", "object oriented programming", "object-oriented");
        registerGroup("solid", "solid principles");
        registerGroup("design patterns", "gang of four", "gof");
        registerGroup("clean architecture", "onion architecture", "hexagonal architecture");
        registerGroup("ddd", "domain driven design", "domain-driven design");
    }

    private static void registerGroup(String primary, String... aliases) {
        String canonical = primary.trim().toLowerCase(Locale.ROOT);
        Set<String> allVariants = new LinkedHashSet<>();
        allVariants.add(canonical);

        for (String alias : aliases) {
            if (alias != null && !alias.isBlank()) {
                allVariants.add(alias.trim().toLowerCase(Locale.ROOT));
            }
        }

        for (String variant : allVariants) {
            SYNONYM_MAP.put(variant, Collections.unmodifiableSet(allVariants));
            CANONICAL_MAP.put(variant, canonical);
        }
    }

    /**
     * Retrieves all synonyms/aliases for the given term (including the term itself).
     * Returns a set containing just the normalized term if no synonyms are registered.
     */
    public static Set<String> getSynonyms(String term) {
        if (term == null || term.isBlank()) return Set.of();
        String norm = term.trim().toLowerCase(Locale.ROOT);
        return SYNONYM_MAP.getOrDefault(norm, Set.of(norm));
    }

    /**
     * Resolves the canonical form of a tech term (e.g. "k8s" -> "kubernetes").
     */
    public static String getCanonical(String term) {
        if (term == null || term.isBlank()) return term;
        String norm = term.trim().toLowerCase(Locale.ROOT);
        return CANONICAL_MAP.getOrDefault(norm, norm);
    }

    /**
     * Checks whether {@code haystack} contains the specified {@code techTerm}
     * OR any of its registered synonyms/aliases using word-boundary safe matching.
     *
     * <p>Example: {@code containsTechOrSynonym("Experience in K8s", "Kubernetes")} -> {@code true}
     */
    public static boolean containsTechOrSynonym(String haystack, String techTerm) {
        if (haystack == null || techTerm == null || haystack.isBlank() || techTerm.isBlank()) {
            return false;
        }

        Set<String> synonyms = getSynonyms(techTerm);
        for (String syn : synonyms) {
            if (TextSanitizationUtil.containsSkillTerm(haystack, syn)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Expands a collection of extracted tech tokens with all their known synonyms.
     */
    public static Set<String> expandTokensWithSynonyms(Collection<String> tokens) {
        if (tokens == null || tokens.isEmpty()) return Set.of();
        Set<String> expanded = new LinkedHashSet<>();
        for (String token : tokens) {
            if (token != null && !token.isBlank()) {
                expanded.addAll(getSynonyms(token));
            }
        }
        return expanded;
    }
}
