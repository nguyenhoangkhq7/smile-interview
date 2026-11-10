"""Canonical Skill Normalizer and Overlap Engine for Stage 6F.3R.

Provides deterministic, auditable canonicalization of skill entities,
preserves semantic distinctness (e.g. C vs C++ vs C#, Java vs JavaScript),
and accurately computes set intersections, Jaccard similarity, and requirement coverage.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, List, Set, Tuple

# Comprehensive alias map to authoritative canonical IDs
CANONICAL_ALIASES: dict[str, str] = {
    # Node.js
    "node.js": "nodejs",
    "node-js": "nodejs",
    "node js": "nodejs",
    "nodejs": "nodejs",
    # Spring Boot
    "spring-boot": "spring-boot",
    "spring boot": "spring-boot",
    "springboot": "spring-boot",
    "spring": "spring-framework",
    "spring framework": "spring-framework",
    # React
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    # React variants (STRICTLY DISTINCT)
    "react-native": "react-native",
    "react native": "react-native",
    "reactnative": "react-native",
    "react-query": "react-query",
    "react query": "react-query",
    # Vue / Angular
    "vue": "vue",
    "vue.js": "vue",
    "vuejs": "vue",
    "vue js": "vue",
    "angular": "angular",
    "angular.js": "angular",
    "angularjs": "angular",
    "angular js": "angular",
    # Kubernetes / Cloud
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "aws",
    "amazon-web-services": "aws",
    "amazon web services": "aws",
    "amazon-aws": "aws",
    "gcp": "gcp",
    "google-cloud": "gcp",
    "google cloud": "gcp",
    "google-cloud-platform": "gcp",
    "google cloud platform": "gcp",
    "azure": "azure",
    "microsoft-azure": "azure",
    "microsoft azure": "azure",
    # CI/CD
    "ci/cd": "ci-cd",
    "ci-cd": "ci-cd",
    "cicd": "ci-cd",
    "ci / cd": "ci-cd",
    "continuous-integration": "ci-cd",
    "continuous integration": "ci-cd",
    # REST API
    "rest-api": "rest-api",
    "rest api": "rest-api",
    "restful-api": "rest-api",
    "restful api": "rest-api",
    "rest-apis": "rest-api",
    "rest apis": "rest-api",
    "restful": "rest-api",
    "rest-api-development": "rest-api",
    "rest api development": "rest-api",
    "restful-api-development": "rest-api",
    "restful api development": "rest-api",
    # AWS Services
    "aws-services": "aws",
    "aws services": "aws",
    # Databases
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "postgre-sql": "postgresql",
    "postgressql": "postgresql",
    "mysql": "mysql",
    "my-sql": "mysql",
    "mongodb": "mongodb",
    "mongo-db": "mongodb",
    "mongo": "mongodb",
    "redis": "redis",
    "sqlite": "sqlite",
    "oracle-database": "oracle-db",
    "oracle database": "oracle-db",
    "oracle db": "oracle-db",
    "sql": "sql",
    "nosql": "nosql",
    "no-sql": "nosql",
    # Programming Languages (STRICTLY DISTINCT)
    "c": "c",
    "c++": "c++",
    "c plus plus": "c++",
    "c-plus-plus": "c++",
    "cplusplus": "c++",
    "cpp": "c++",
    "c#": "c#",
    "c sharp": "c#",
    "c-sharp": "c#",
    "csharp": "c#",
    ".net": ".net",
    "dotnet": ".net",
    ".net core": ".net",
    "dotnet core": ".net",
    "asp.net": ".net",
    "asp.net core": ".net",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "python": "python",
    "python3": "python",
    "python 3": "python",
    "golang": "golang",
    "go": "golang",
    "ruby": "ruby",
    "ruby on rails": "ruby-on-rails",
    "rails": "ruby-on-rails",
    "php": "php",
    "scala": "scala",
    "kotlin": "kotlin",
    "swift": "swift",
    "rust": "rust",
    # State Management & Libraries (STRICTLY DISTINCT)
    "redux": "redux",
    "redux-toolkit": "redux-toolkit",
    "mobx": "mobx",
    "graphql": "graphql",
    "apollo": "apollo-graphql",
    "tailwind": "tailwind-css",
    "tailwind-css": "tailwind-css",
    "tailwindcss": "tailwind-css",
    "bootstrap": "bootstrap",
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "sass": "sass",
    "scss": "sass",
    # DevOps / Infrastructure
    "docker": "docker",
    "terraform": "terraform",
    "ansible": "ansible",
    "jenkins": "jenkins",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "linux": "linux",
    "unix": "unix",
    # Big Data & ML
    "kafka": "kafka",
    "apache-kafka": "kafka",
    "apache kafka": "kafka",
    "spark": "apache-spark",
    "apache-spark": "apache-spark",
    "apache spark": "apache-spark",
    "airflow": "apache-airflow",
    "apache-airflow": "apache-airflow",
    "apache airflow": "apache-airflow",
    "hadoop": "hadoop",
    "apache-hadoop": "hadoop",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "databricks": "databricks",
    "dbt": "dbt",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "pandas": "pandas",
    "numpy": "numpy",
    # BI & Analytics
    "tableau": "tableau",
    "tableau-desktop": "tableau",
    "tableau desktop": "tableau",
    "tableau-server": "tableau",
    "tableau server": "tableau",
    "power-bi": "power-bi",
    "power bi": "power-bi",
    "powerbi": "power-bi",
    # Testing
    "selenium": "selenium",
    "cypress": "cypress",
    "junit": "junit",
    "pytest": "pytest",
}

# Regex to safely preserve characters: alphanumeric, +, #, ., -
SAFE_CHAR_REGEX = re.compile(r"[^a-z0-9+#.\-]+")
CONSECUTIVE_HYPHENS_REGEX = re.compile(r"-{2,}")


def normalize_canonical_skill(skill: Any) -> str:
    """Normalize a skill mention into a stable, canonical skill identifier.

    Invariants:
    - Unicode NFKC normalization and lowercased.
    - Preserves semantic distinctions: 'c' != 'c++' != 'c#', 'java' != 'javascript',
      'redis' != 'redux', 'sql' != 'nosql', 'react' != 'react-query'.
    - Maps common abbreviations/aliases (k8s -> kubernetes, aws -> aws, ci/cd -> ci-cd).
    """
    if skill is None:
        return ""
    if not isinstance(skill, str):
        skill = str(skill)

    # 1. Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", skill).strip()
    if not text:
        return ""

    # 2. Lowercase / casefold
    lower = text.casefold()

    # 3. Check alias dictionary directly
    if lower in CANONICAL_ALIASES:
        return CANONICAL_ALIASES[lower]

    # 4. Standard clean: replace slashes and underscores with hyphens
    cleaned = lower.replace("/", "-").replace("_", "-")

    # If it now matches alias dictionary
    if cleaned in CANONICAL_ALIASES:
        return CANONICAL_ALIASES[cleaned]

    # 5. Remove unwanted punctuation while preserving +, #, ., -
    cleaned = SAFE_CHAR_REGEX.sub("-", cleaned)
    cleaned = CONSECUTIVE_HYPHENS_REGEX.sub("-", cleaned).strip("-")

    # Re-check alias dictionary
    if cleaned in CANONICAL_ALIASES:
        return CANONICAL_ALIASES[cleaned]

    return cleaned


def compute_canonical_overlap(
    cv_skills: Iterable[Any] | None,
    jd_skills: Iterable[Any] | None,
) -> Tuple[int, float, float, List[str]]:
    """Compute deterministic canonical skill overlap metrics.

    Args:
        cv_skills: Sequence of CV skill strings or objects with 'skill_id'.
        jd_skills: Sequence of JD skill strings or objects with 'skill_id'.

    Returns:
        Tuple containing:
            1. overlap_count (int): Number of overlapping canonical skills.
            2. jaccard_index (float): len(intersection) / len(union).
            3. jd_coverage (float): len(intersection) / len(jd_skills).
            4. overlapping_skills (List[str]): Sorted canonical skill identifiers.
    """
    def _extract_canonical_set(skills: Iterable[Any] | None) -> Set[str]:
        if not skills:
            return set()
        cset = set()
        for s in skills:
            if isinstance(s, dict):
                s_str = s.get("skill_id") or s.get("name") or ""
            else:
                s_str = str(s)
            canon = normalize_canonical_skill(s_str)
            if canon:
                cset.add(canon)
        return cset

    cv_set = _extract_canonical_set(cv_skills)
    jd_set = _extract_canonical_set(jd_skills)

    if not cv_set or not jd_set:
        return 0, 0.0, 0.0, []

    intersection = cv_set.intersection(jd_set)
    union = cv_set.union(jd_set)

    overlap_count = len(intersection)
    jaccard_index = round(overlap_count / len(union), 4) if union else 0.0
    jd_coverage = round(overlap_count / len(jd_set), 4) if jd_set else 0.0
    overlapping_skills = sorted(list(intersection))

    return overlap_count, jaccard_index, jd_coverage, overlapping_skills
