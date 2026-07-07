package fit.iuh.modules.assessment;

/**
 * Categorizes the primary engineering domain of the Job Description.
 *
 * <p>Extracted via {@code MetadataExtractionService} from the JD Markdown using a
 * lightweight LLM call that must output exactly one of these values (case-insensitive).
 * Stored as a {@code VARCHAR} column via {@code @Enumerated(EnumType.STRING)}.
 *
 * <p>The hierarchical rule engine in {@code job_categories} mirrors this ENUM structure.
 * Every leaf node in the DB tree corresponds to one of these enum constants.
 */
public enum JobCategory {

    /** Java, Go, Python, Node.js — server-side, APIs, microservices, databases */
    BACKEND,

    /** React, Vue, Angular, CSS — browser-side, UI, SPAs */
    FRONTEND,

    /** Both backend and frontend responsibilities in the same role */
    FULLSTACK,

    /** CI/CD, Kubernetes, Docker, infrastructure-as-code, SRE */
    DEVOPS,

    /** ETL/ELT pipelines, Spark, Kafka, Airflow, data warehousing */
    DATA_ENGINEERING,

    /** Model training, MLOps, feature engineering, model serving */
    ML_ENGINEERING,

    /** iOS (Swift), Android (Kotlin/Java), React Native, Flutter */
    MOBILE,

    /** Penetration testing, SAST/DAST, secure coding, compliance */
    SECURITY,

    /** Test automation, QA frameworks, performance testing */
    QA,

    /** Fallback when the JD does not clearly fit any known category */
    OTHER
}
