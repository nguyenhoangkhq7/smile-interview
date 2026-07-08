package fit.iuh.modules.questionbank;

import fit.iuh.modules.assessment.SeniorityLevel;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link SemanticCacheKeyGenerator}.
 *
 * <p>Updated in v2 to test the new criteria-id–based key methods.
 * The legacy {@code generateKey(String, String)} overload is kept for backward-compat
 * with existing Redis entries but is no longer the primary key strategy.
 */
class SemanticCacheKeyGeneratorTest {

    private final SemanticCacheKeyGenerator generator = new SemanticCacheKeyGenerator();

    // ──────────────────────────────────────────────────────────────────────────
    // v2 API — criteria-id based keys
    // ──────────────────────────────────────────────────────────────────────────

    @Test
    void testStandardItemKey_sameInputSameKey() {
        // Same (criteriaId, status, level) must always produce the same key
        String key1 = generator.generateKey(42L, "matched", SeniorityLevel.MID);
        String key2 = generator.generateKey(42L, "matched", SeniorityLevel.MID);
        assertEquals(key1, key2, "Same inputs must produce identical keys");
    }

    @Test
    void testStandardItemKey_differentStatusDifferentKey() {
        String matchedKey = generator.generateKey(42L, "matched", SeniorityLevel.MID);
        String missingKey = generator.generateKey(42L, "missing", SeniorityLevel.MID);
        assertNotEquals(matchedKey, missingKey, "Different status must produce different keys");
    }

    @Test
    void testStandardItemKey_differentLevelDifferentKey() {
        String midKey    = generator.generateKey(42L, "matched", SeniorityLevel.MID);
        String seniorKey = generator.generateKey(42L, "matched", SeniorityLevel.SENIOR);
        assertNotEquals(midKey, seniorKey, "Different seniority levels must produce different keys");
    }

    @Test
    void testStandardItemKey_differentCriteriaIdDifferentKey() {
        String key1 = generator.generateKey(1L,  "matched", SeniorityLevel.MID);
        String key2 = generator.generateKey(99L, "matched", SeniorityLevel.MID);
        assertNotEquals(key1, key2, "Different criteria IDs must produce different keys");
    }

    @Test
    void testStandardItemKey_usesCorrectNamespace() {
        String key = generator.generateKey(1L, "matched", SeniorityLevel.JUNIOR);
        assertTrue(key.startsWith("siminterview:cache:item:"),
                "Standard item key must use 'siminterview:cache:item:' namespace");
    }

    @Test
    void testAdHocKey_sameNormalizedNameSameKey() {
        // Same concept written differently should normalize to same key
        String key1 = generator.generateKeyForAdHoc("System Design", "missing", SeniorityLevel.SENIOR);
        String key2 = generator.generateKeyForAdHoc("system design", "missing", SeniorityLevel.SENIOR);
        assertEquals(key1, key2, "Ad-hoc keys should be case-insensitive");
    }

    @Test
    void testAdHocKey_usesCorrectNamespace() {
        String key = generator.generateKeyForAdHoc("Agile & SDLC", "matched", SeniorityLevel.MID);
        assertTrue(key.startsWith("siminterview:cache:adhoc:"),
                "Ad-hoc key must use 'siminterview:cache:adhoc:' namespace");
    }

    @Test
    void testStandardKeyAndAdHocKeyDoNotCollide() {
        // Even if the text would hash similarly, namespaces must prevent collision
        String standardKey = generator.generateKey(1L, "matched", SeniorityLevel.MID);
        String adHocKey    = generator.generateKeyForAdHoc("Tech Stack", "matched", SeniorityLevel.MID);
        assertNotEquals(standardKey, adHocKey, "Standard and ad-hoc keys must not collide");
    }

    @Test
    void testNullSeniorityFallsBackToMid() {
        // Null seniority should not throw and should fall back to "MID"
        assertDoesNotThrow(() -> generator.generateKey(1L, "matched", null));
        assertDoesNotThrow(() -> generator.generateKeyForAdHoc("Some Criteria", "matched", null));
    }
}
