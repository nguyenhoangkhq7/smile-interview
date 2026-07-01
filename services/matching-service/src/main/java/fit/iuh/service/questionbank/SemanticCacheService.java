package fit.iuh.service.questionbank;

import fit.iuh.dto.questionbank.QuestionDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;

/**
 * Handles operations to read and write generated question banks from/to Redis cache.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SemanticCacheService {

    private final RedisTemplate<String, List<QuestionDto>> questionCacheRedisTemplate;

    /**
     * Retrieves cached questions for a given key.
     * Returns null if key does not exist or Redis is unavailable.
     */
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

    /**
     * Caches questions for a given key with a defined Time-To-Live (TTL).
     */
    public void put(String key, List<QuestionDto> questions, Duration ttl) {
        try {
            questionCacheRedisTemplate.opsForValue().set(key, questions, ttl);
            log.info("[RedisCache] Cache WRITE success for key: {}, TTL: {}", key, ttl);
        } catch (Exception e) {
            log.error("[RedisCache] Failed to write cache for key {}: {}", key, e.getMessage());
        }
    }
}
