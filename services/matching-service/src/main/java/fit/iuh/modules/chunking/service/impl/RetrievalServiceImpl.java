package fit.iuh.modules.chunking.service.impl;

import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.chunking.service.EmbeddingService;
import fit.iuh.modules.chunking.service.RetrievalService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class RetrievalServiceImpl implements RetrievalService {

    private static final int RRF_K = 60;

    private final DocumentChunkRepository documentChunkRepository;
    private final EmbeddingService embeddingService;

    @Override
    @Transactional(readOnly = true)
    public List<DocumentChunk> retrieveRelevantChunks(String sessionId, String docType, String queryText, int topK) {
        if (sessionId == null || queryText == null || queryText.isBlank()) {
            return Collections.emptyList();
        }

        // 1. Dense Vector Search
        List<DocumentChunk> denseResults = Collections.emptyList();
        try {
            float[] queryVector = embeddingService.embedQuery(queryText);
            if (queryVector != null) {
                String vectorString = formatVectorForPg(queryVector);
                denseResults = documentChunkRepository.searchDense(sessionId, docType, vectorString, Math.max(topK * 2, 10));
                if (denseResults == null) denseResults = Collections.emptyList();
            } else {
                log.warn("[Retrieval] EmbedQuery returned null (Ollama might be down). Skipping dense search for query='{}'", queryText);
            }
        } catch (Exception e) {
            log.warn("[Retrieval] Dense vector search warning for session={}: {}", sessionId, e.getMessage());
        }

        // 2. Sparse Keyword Search (FTS / ILIKE)
        List<DocumentChunk> sparseResults = Collections.emptyList();
        try {
            String cleanQuery = queryText.replaceAll("[^a-zA-Z0-9\\s]", " ").replaceAll("\\s+", " ").trim();
            if (cleanQuery.isBlank()) cleanQuery = queryText;
            sparseResults = documentChunkRepository.searchSparse(sessionId, docType, cleanQuery, Math.max(topK * 2, 10));
            if (sparseResults == null) sparseResults = Collections.emptyList();
        } catch (Exception e) {
            log.warn("[Retrieval] Sparse keyword search warning for session={}: {}", sessionId, e.getMessage());
        }

        // 3. RRF Rank Fusion (in Java)
        Map<UUID, Double> rrfScores = new HashMap<>();
        Map<UUID, DocumentChunk> chunkMap = new HashMap<>();

        for (int rank = 0; rank < denseResults.size(); rank++) {
            DocumentChunk chunk = denseResults.get(rank);
            chunkMap.put(chunk.getId(), chunk);
            double score = 1.0 / (RRF_K + rank + 1);
            rrfScores.put(chunk.getId(), rrfScores.getOrDefault(chunk.getId(), 0.0) + score);
        }

        for (int rank = 0; rank < sparseResults.size(); rank++) {
            DocumentChunk chunk = sparseResults.get(rank);
            chunkMap.put(chunk.getId(), chunk);
            double score = 1.0 / (RRF_K + rank + 1);
            rrfScores.put(chunk.getId(), rrfScores.getOrDefault(chunk.getId(), 0.0) + score);
        }

        List<DocumentChunk> fusedList = rrfScores.entrySet().stream()
                .sorted(Map.Entry.<UUID, Double>comparingByValue().reversed())
                .map(entry -> chunkMap.get(entry.getKey()))
                .filter(Objects::nonNull)
                .limit(topK)
                .collect(Collectors.toList());

        log.debug("[Retrieval] Hybrid RRF search for query='{}' returned {} chunks", queryText, fusedList.size());
        return fusedList;
    }

    @Override
    @Transactional(readOnly = true)
    public String retrieveRelevantCvContext(String sessionId, List<String> criteriaSkills, int maxChunks) {
        if (criteriaSkills == null || criteriaSkills.isEmpty()) {
            return "";
        }

        if (!documentChunkRepository.existsBySessionId(sessionId)) {
            log.debug("[Retrieval] No chunks found in DB for session={}", sessionId);
            return "";
        }

        Set<UUID> selectedChunkIds = new LinkedHashSet<>();
        List<DocumentChunk> retrievedChildChunks = new ArrayList<>();

        for (String skill : criteriaSkills) {
            if (skill == null || skill.isBlank()) continue;
            List<DocumentChunk> matches = retrieveRelevantChunks(sessionId, "cv", skill, 2);
            for (DocumentChunk m : matches) {
                if (selectedChunkIds.add(m.getId())) {
                    retrievedChildChunks.add(m);
                }
                if (retrievedChildChunks.size() >= maxChunks) break;
            }
            if (retrievedChildChunks.size() >= maxChunks) break;
        }

        if (retrievedChildChunks.isEmpty()) {
            List<DocumentChunk> allCvChunks = documentChunkRepository.findBySessionIdAndDocType(sessionId, "cv");
            retrievedChildChunks = allCvChunks.stream().limit(maxChunks).collect(Collectors.toList());
        }

        // Collect parents
        Set<UUID> parentIds = retrievedChildChunks.stream()
                .map(DocumentChunk::getParentId)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());

        Map<UUID, String> parentContentMap = new HashMap<>();
        if (!parentIds.isEmpty()) {
            List<DocumentChunk> parents = documentChunkRepository.findAllById(parentIds);
            for (DocumentChunk p : parents) {
                // STRICT SAFEGUARD: Use content (original CV text), NEVER enrichedContent
                parentContentMap.put(p.getId(), p.getContent());
            }
        }

        // Group child chunks by parentId
        Map<UUID, List<DocumentChunk>> groupedChunks = new LinkedHashMap<>();
        List<DocumentChunk> flatChunks = new ArrayList<>();
        
        for (DocumentChunk child : retrievedChildChunks) {
            if (child.getParentId() != null) {
                groupedChunks.computeIfAbsent(child.getParentId(), k -> new ArrayList<>()).add(child);
            } else {
                flatChunks.add(child);
            }
        }

        StringBuilder sb = new StringBuilder();
        sb.append("====== CANDIDATE CV (RELEVANT CONTEXT CHUNKS) ======\n");

        for (Map.Entry<UUID, List<DocumentChunk>> entry : groupedChunks.entrySet()) {
            UUID pId = entry.getKey();
            List<DocumentChunk> children = entry.getValue();

            if (parentContentMap.containsKey(pId)) {
                sb.append("[PROJECT CONTEXT]: ").append(parentContentMap.get(pId)).append("\n");
                for (DocumentChunk child : children) {
                    sb.append("- [SPECIFIC CV SNIPPET]: ").append(child.getContent()).append("\n");
                }
                sb.append("\n");
            } else {
                for (DocumentChunk child : children) {
                    sb.append("- [SPECIFIC CV SNIPPET]: ").append(child.getContent()).append("\n");
                }
                sb.append("\n");
            }
        }

        for (DocumentChunk flat : flatChunks) {
            sb.append("[GENERAL SNIPPET]: ").append(flat.getContent()).append("\n\n");
        }

        return sb.toString().strip();
    }

    private String formatVectorForPg(float[] vector) {
        if (vector == null || vector.length == 0) return "[]";
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < vector.length; i++) {
            sb.append(vector[i]);
            if (i < vector.length - 1) sb.append(",");
        }
        sb.append("]");
        return sb.toString();
    }
}
