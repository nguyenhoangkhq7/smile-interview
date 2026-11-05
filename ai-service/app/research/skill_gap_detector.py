from typing import Dict, List, Tuple
from app.research.models import SkillGraphMatchResult, SkillGapResult, SkillNode


class SkillGapDetector:
    """
    [Đóng góp khoa học 2]:
    Thuật toán xác định 'Khoảng trống năng lực' (Skill-Gap Detection) và 'Điểm nghi vấn'
    giữa CV và JD dựa trên cấu trúc đồ thị phụ thuộc kỹ năng GNN.
    """

    def detect_gaps(self, graph_result: SkillGraphMatchResult) -> List[SkillGapResult]:
        node_map: Dict[str, SkillNode] = {n.name: n for n in graph_result.nodes}
        prereq_map: Dict[str, List[str]] = {n.name: [] for n in graph_result.nodes}

        for edge in graph_result.edges:
            if edge.target_skill in prereq_map:
                prereq_map[edge.target_skill].append(edge.source_skill)

        gaps: List[SkillGapResult] = []
        for node in graph_result.nodes:
            prereqs = prereq_map.get(node.name, [])
            weak_prereqs = [
                p for p in prereqs
                if p in node_map and node_map[p].match_status in ("missing", "weak")
            ]

            if node.match_status == "matched" and weak_prereqs:
                gaps.append(
                    SkillGapResult(
                        skill_name=node.name,
                        gap_type="UNVERIFIED_CLAIM",
                        severity=0.85,
                        prerequisite_chain=tuple(weak_prereqs + [node.name]),
                        explanation=(
                            f"Ứng viên nêu có '{node.name}' trong CV nhưng thiếu bằng chứng nền tảng "
                            f"phụ thuộc ({', '.join(weak_prereqs)}) trên đồ thị kỹ năng."
                        ),
                        actionable_recommendation=(
                            f"Cần bổ sung minh chứng thực tế về {', '.join(weak_prereqs)} khi triển khai {node.name} "
                            f"và chuẩn bị cho câu hỏi kiểm chứng chuyên sâu."
                        ),
                    )
                )
            elif node.match_status == "missing":
                severity = 0.95 if node.is_mandatory else 0.60
                gaps.append(
                    SkillGapResult(
                        skill_name=node.name,
                        gap_type="CRITICAL_MISSING" if node.is_mandatory else "OPTIONAL_MISSING",
                        severity=severity,
                        prerequisite_chain=tuple(prereqs + [node.name]),
                        explanation=f"Kỹ năng '{node.name}' yêu cầu trong JD nhưng chưa xuất hiện trong CV.",
                        actionable_recommendation=(
                            f"Bổ sung dự án hoặc kinh nghiệm thực hành liên quan đến {node.name} "
                            f"để lấp khoảng trống năng lực so với JD."
                        ),
                    )
                )
            elif node.match_status in ("weak", "partial"):
                gaps.append(
                    SkillGapResult(
                        skill_name=node.name,
                        gap_type="WEAK_PREREQUISITE",
                        severity=0.75 if node.is_mandatory else 0.50,
                        prerequisite_chain=tuple(prereqs + [node.name]),
                        explanation=(
                            f"Mức độ tương đồng GNN của '{node.name}' còn hạn chế ({int(node.gnn_aggregated_score * 100)}%), "
                            f"chưa nêu bật độ sâu kỹ thuật."
                        ),
                        actionable_recommendation=(
                            f"Làm rõ quy mô dự án, kiến trúc và kết quả định lượng khi sử dụng {node.name} trong CV."
                        ),
                    )
                )

        gaps.sort(key=lambda g: g.severity, reverse=True)
        return gaps
