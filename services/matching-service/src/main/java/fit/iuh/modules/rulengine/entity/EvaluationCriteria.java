package fit.iuh.modules.rulengine.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "evaluation_criteria")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EvaluationCriteria {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false, nullable = false)
    private Long id;

    @Column(name = "name", nullable = false, length = 150)
    private String name;

    @Column(name = "category", nullable = false, length = 50)
    private String category;

    @Column(name = "question_type", nullable = false, length = 50)
    private String questionType;

    @Column(name = "prompt_instruction", columnDefinition = "TEXT")
    private String promptInstruction;
}
