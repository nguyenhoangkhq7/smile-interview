package fit.iuh.modules.questionbank.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "questions")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Question {

    @Id
    @Column(name = "id", updatable = false, nullable = false, length = 50)
    private String id; // Use String for Q001, etc. instead of UUID

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_question_id", nullable = false)
    private QuestionBank questionBank;

    @Column(name = "category", length = 100)
    private String category;

    @Column(name = "question_type", length = 100)
    private String questionType;

    @Column(name = "expected_competency", length = 200)
    private String expectedCompetency;

    @Column(name = "question_text", columnDefinition = "TEXT")
    private String questionText;

    @Column(name = "expected_answer", columnDefinition = "TEXT")
    private String expectedAnswer;

    @Column(name = "difficulty", length = 50)
    private String difficulty;

    @Column(name = "topic", length = 150)
    private String topic;

    @Column(name = "details", columnDefinition = "TEXT")
    private String details;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPrePersist() {
        if (this.createdAt == null) {
            this.createdAt = LocalDateTime.now();
        }
    }
}
