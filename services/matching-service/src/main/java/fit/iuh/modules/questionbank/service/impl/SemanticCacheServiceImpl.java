package fit.iuh.modules.questionbank.service.impl;

import fit.iuh.modules.questionbank.dto.QuestionDto;
import fit.iuh.modules.questionbank.service.SemanticCacheService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class SemanticCacheServiceImpl implements SemanticCacheService {

    private final RedisTemplate<String, List<QuestionDto>> questionCacheRedisTemplate;

    @Override
    public List<QuestionDto> get(String key) {
        try {
            List<QuestionDto> cached = questionCacheRedisTemplate.opsForValue().get(key);
            if (cached != null) {
                log.info("[RedisCache] Cache HIT for key: {}", key);
                return cached;
            }
        } catch (Exception e) {
            log.error("[RedisCache] Failed to read cache for key {}: {}", key, e.getMessage());
        }
        log.info("[RedisCache] Cache MISS for key: {}", key);
        return null;
    }

    @Override
    public void put(String key, List<QuestionDto> questions, Duration ttl) {
        try {
            questionCacheRedisTemplate.opsForValue().set(key, questions, ttl);
            log.info("[RedisCache] Cache WRITE success for key: {}, TTL: {}", key, ttl);
        } catch (Exception e) {
            log.error("[RedisCache] Failed to write cache for key {}: {}", key, e.getMessage());
        }
    }
}
