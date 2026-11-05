package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.questionbank.dto.QuestionDto;

import java.time.Duration;
import java.util.List;

public interface SemanticCacheService {

    List<QuestionDto> get(String key);

    void put(String key, List<QuestionDto> questions, Duration ttl);
}
