package fit.iuh.modules.matching.controller;

import fit.iuh.modules.matching.client.SemanticMatchingClient;
import fit.iuh.modules.matching.dto.MatchingDtos.MatchRequestDto;
import fit.iuh.modules.matching.dto.MatchingDtos.Module1OutputDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * REST Controller for Contribution 1: Semantic Similarity Metric (Sentence-BERT + GNN).
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/matching")
@RequiredArgsConstructor
public class SemanticMatchingController {

    private final SemanticMatchingClient matchingClient;

    @PostMapping(value = "/compare", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Module1OutputDto> compareCvAndJd(@RequestBody MatchRequestDto request) {
        log.info("[SemanticMatchingController] Compare request received");
        Module1OutputDto output = matchingClient.match(request.cvText(), request.jdText());
        return ResponseEntity.ok(output);
    }
}
