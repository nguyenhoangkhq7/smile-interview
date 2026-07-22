package fit.iuh.modules.questionbank.controller;

import fit.iuh.modules.questionbank.dto.GenerateQuestionBankRequest;
import fit.iuh.modules.questionbank.dto.QuestionBankResponseDto;
import fit.iuh.modules.questionbank.service.QuestionBankService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/question-bank")
@RequiredArgsConstructor
public class QuestionBankController {

    private final QuestionBankService questionBankService;

    @PostMapping(value = "/generate", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<QuestionBankResponseDto> generate(@Valid @RequestBody GenerateQuestionBankRequest request) {
        log.info("Received request to generate question bank for sessionId={}", request.getSessionId());
        QuestionBankResponseDto response = questionBankService.generate(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping(value = "/session/{sessionId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<QuestionBankResponseDto>> getBySessionId(@PathVariable String sessionId) {
        log.info("Received request to fetch question banks for sessionId={}", sessionId);
        List<QuestionBankResponseDto> list = questionBankService.getBySessionId(sessionId);
        return ResponseEntity.ok(list);
    }

    @GetMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<QuestionBankResponseDto> getById(@PathVariable UUID id) {
        log.info("Received request to fetch question bank by ID={}", id);
        QuestionBankResponseDto response = questionBankService.getById(id);
        return ResponseEntity.ok(response);
    }

    @PostMapping(value = "/{questionBankId}/regenerate/{questionId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<QuestionBankResponseDto> regenerateQuestion(
            @PathVariable UUID questionBankId,
            @PathVariable String questionId) {
        log.info("Received request to regenerate question {} in question bank {}", questionId, questionBankId);
        QuestionBankResponseDto response = questionBankService.regenerateQuestion(questionBankId, questionId);
        return ResponseEntity.ok(response);
    }
}
