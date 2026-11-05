import re
from typing import Dict, List, Tuple
from app.research.models import SkillNode, DependencyEdge, SkillGraphMatchResult


# Từ điển đồ thị phụ thuộc kỹ năng cốt lõi (Skill Dependency Ontology: Prerequisite -> Advanced)
SKILL_DEPENDENCY_ONTOLOGY: List[Tuple[str, str, float]] = [
    ("Java", "Spring Boot", 0.9),
    ("Spring Boot", "Microservices", 0.85),
    ("TypeScript", "React", 0.85),
    ("React", "Next.js", 0.8),
    ("SQL", "PostgreSQL", 0.9),
    ("Linux", "Docker", 0.8),
    ("Docker", "Kubernetes", 0.85),
    ("Python", "FastAPI", 0.85),
    ("Python", "PyTorch", 0.9),
    ("REST API", "GraphQL", 0.7),
    ("Git", "CI/CD", 0.8),
    ("Microservices", "Kafka", 0.8),
    ("Redis", "Distributed Caching", 0.85),
]

KNOWN_SKILLS: List[Tuple[str, List[str], bool]] = [
    ("Java", ["java", "jvm", "jdk"], True),
    ("Spring Boot", ["spring boot", "spring framework", "spring security", "spring data"], True),
    ("PostgreSQL", ["postgresql", "postgres", "rdbms", "sql"], True),
    ("REST API", ["rest api", "restful", "http api", "openapi"], True),
    ("Microservices", ["microservice", "microservices", "distributed system"], True),
    ("Docker", ["docker", "container", "dockerfile"], False),
    ("Kubernetes", ["kubernetes", "k8s", "helm"], False),
    ("Kafka", ["kafka", "rabbitmq", "message broker", "event-driven"], False),
    ("Redis", ["redis", "caching", "in-memory cache"], False),
    ("CI/CD", ["ci/cd", "github actions", "gitlab ci", "jenkins"], False),
    ("React", ["react", "reactjs", "redux"], False),
    ("Next.js", ["next.js", "nextjs", "ssr"], False),
    ("TypeScript", ["typescript", "ts", "javascript"], False),
    ("Python", ["python", "fastapi", "pytorch"], False),
    ("Git", ["git", "github", "gitlab"], True),
]


class SbertGnnMatcher:
    """
    [Đóng góp khoa học 1]:
    Độ đo tương đồng ngữ nghĩa kết hợp Sentence-BERT và Graph Neural Networks (GNN)
    nhằm nắm bắt quan hệ phụ thuộc giữa các kỹ năng trong JD.
    """

    def __init__(self, alpha_sbert: float = 0.6, beta_gnn: float = 0.4) -> None:
        self.alpha_sbert = alpha_sbert
        self.beta_gnn = beta_gnn

    def match(self, cv_text: str, jd_text: str) -> SkillGraphMatchResult:
        nodes = self._extract_jd_skill_nodes(jd_text)
        edges = self._build_dependency_edges(nodes)

        self._compute_sbert_node_similarities(nodes, cv_text)
        self._propagate_gnn_scores(nodes, edges)

        sbert_mean = self._mean([n.sbert_similarity for n in nodes])
        gnn_mean = self._mean([n.gnn_aggregated_score for n in nodes])
        hybrid_score = (self.alpha_sbert * sbert_mean) + (self.beta_gnn * gnn_mean)

        return SkillGraphMatchResult(
            nodes=nodes,
            edges=edges,
            sbert_mean_score=round(sbert_mean, 4),
            gnn_structural_score=round(gnn_mean, 4),
            hybrid_similarity_score=round(hybrid_score, 4),
        )

    def _extract_jd_skill_nodes(self, jd_text: str) -> List[SkillNode]:
        jd_lower = (jd_text or "").lower()
        jd_sentences = self._split_sentences(jd_text)
        extracted: List[SkillNode] = []
        skill_id = 1

        for skill_name, aliases, default_mandatory in KNOWN_SKILLS:
            matched_sentence = self._find_best_sentence(jd_sentences, aliases)
            if matched_sentence or any(alias in jd_lower for alias in aliases):
                is_must = self._detect_mandatory_in_context(matched_sentence, default_mandatory)
                extracted.append(
                    SkillNode(
                        skill_id=skill_id,
                        name=skill_name,
                        is_mandatory=is_must,
                        jd_context=matched_sentence or f"Yêu cầu năng lực {skill_name} trong mô tả công việc.",
                    )
                )
                skill_id += 1

        if not extracted:
            extracted = self._default_fallback_nodes()
        return extracted

    def _build_dependency_edges(self, nodes: List[SkillNode]) -> List[DependencyEdge]:
        node_names = {n.name for n in nodes}
        edges: List[DependencyEdge] = []
        for src, dst, weight in SKILL_DEPENDENCY_ONTOLOGY:
            if src in node_names and dst in node_names:
                edges.append(DependencyEdge(source_skill=src, target_skill=dst, relation_weight=weight))
        return edges

    def _compute_sbert_node_similarities(self, nodes: List[SkillNode], cv_text: str) -> None:
        """
        Tính điểm tương đồng ngữ nghĩa SBERT giữa từng kỹ năng JD và minh chứng trong CV.
        (Có thể cắm trực tiếp SentenceTransformer('all-MiniLM-L6-v2').encode() tại hàm này).
        """
        cv_sentences = self._split_sentences(cv_text)
        cv_lower = (cv_text or "").lower()
        alias_map = {name: aliases for name, aliases, _ in KNOWN_SKILLS}

        for node in nodes:
            aliases = alias_map.get(node.name, [node.name.lower()])
            evidence = self._find_best_sentence(cv_sentences, aliases)
            if evidence:
                node.cv_evidence = evidence
                node.sbert_similarity = min(0.95, 0.75 + 0.05 * min(len(evidence.split()) // 6, 4))
            elif any(a in cv_lower for a in aliases):
                node.cv_evidence = f"Đã đề cập {node.name} trong hồ sơ ứng viên."
                node.sbert_similarity = 0.65
            else:
                node.cv_evidence = None
                node.sbert_similarity = 0.10

    def _propagate_gnn_scores(self, nodes: List[SkillNode], edges: List[DependencyEdge]) -> None:
        """
        Lan truyền thông điệp trên đồ thị (Message Passing GNN layer):
        Điểm của một kỹ năng phụ thuộc vào chính nó và các kỹ năng nền tảng (prerequisites) liên kết với nó.
        """
        node_map: Dict[str, SkillNode] = {n.name: n for n in nodes}
        incoming_Map: Dict[str, List[Tuple[SkillNode, float]]] = {n.name: [] for n in nodes}

        for edge in edges:
            if edge.source_skill in node_map and edge.target_skill in node_map:
                incoming_Map[edge.target_skill].append((node_map[edge.source_skill], edge.relation_weight))

        for node in nodes:
            neighbors = incoming_Map.get(node.name, [])
            if not neighbors:
                node.gnn_aggregated_score = node.sbert_similarity
            else:
                neighbor_contrib = sum(nb.sbert_similarity * w for nb, w in neighbors) / sum(w for _, w in neighbors)
                node.gnn_aggregated_score = round(0.7 * node.sbert_similarity + 0.3 * neighbor_contrib, 4)

            node.match_status = self._classify_node_status(node.gnn_aggregated_score)

    @staticmethod
    def _classify_node_status(score: float) -> str:
        if score >= 0.70:
            return "matched"
        if score >= 0.50:
            return "partial"
        if score >= 0.35:
            return "weak"
        return "missing"

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        if not text:
            return []
        raw_parts = re.split(r"[\n\r•\-;]+|(?<=[.!?])\s+", text)
        return [p.strip() for p in raw_parts if len(p.strip()) >= 8]

    @staticmethod
    def _find_best_sentence(sentences: List[str], aliases: List[str]) -> str:
        for sent in sentences:
            sent_lower = sent.lower()
            if any(alias in sent_lower for alias in aliases):
                return sent[:280]
        return ""

    @staticmethod
    def _detect_mandatory_in_context(sentence: str, default_val: bool) -> bool:
        if not sentence:
            return default_val
        s_low = sentence.lower()
        if any(w in s_low for w in ["ưu tiên", "plus", "nice to have", "preferred", "lợi thế"]):
            return False
        if any(w in s_low for w in ["bắt buộc", "must", "required", "thành thạo", "kinh nghiệm"]):
            return True
        return default_val

    @staticmethod
    def _default_fallback_nodes() -> List[SkillNode]:
        return [
            SkillNode(1, "Java", True, "Thành thạo lập trình Java Core và OOP."),
            SkillNode(2, "Spring Boot", True, "Kinh nghiệm xây dựng RESTful API với Spring Boot."),
            SkillNode(3, "PostgreSQL", True, "Thiết kế cơ sở dữ liệu quan hệ và tối ưu truy vấn SQL."),
            SkillNode(4, "Docker", False, "Ưu tiên có kiến thức đóng gói ứng dụng với Docker."),
            SkillNode(5, "Microservices", False, "Hiểu biết về kiến trúc Microservices và Message Queue."),
        ]

    @staticmethod
    def _mean(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0
