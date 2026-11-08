package fit.iuh.modules.session.service.impl;

import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.SessionResponse.SessionTurnDto;
import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.entity.SessionTurn;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
import fit.iuh.modules.session.repository.ResumeRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import fit.iuh.modules.session.service.SessionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class SessionServiceImpl implements SessionService {

    private final SessionRepository sessionRepository;
    private final ResumeRepository resumeRepository;
    private final JobDescriptionRepository jobDescriptionRepository;
    private final SessionTurnRepository sessionTurnRepository;
    private final fit.iuh.modules.evidence.InterviewRunRepository evidenceRuns;

    @Override
    @Transactional
    public SessionResponse createSession(UUID userId, CreateSessionRequest request) {
        String sessionId = (request.getId() != null && !request.getId().isBlank())
                ? request.getId()
                : "session-" + System.currentTimeMillis();

        log.info("[SessionService] Creating/Upserting session: id={}, userId={}, roleTitle={}", sessionId, userId, request.getRoleTitle());

        Session session = sessionRepository.lockById(sessionId).orElse(null);
        requireLegacyWrite(sessionId);
        if (session == null) {
            session = Session.builder()
                    .id(sessionId)
                    .userId(userId)
                    .startedAt(LocalDateTime.now())
                    .status(request.getStatus() != null ? request.getStatus() : "Not started")
                    .build();
        }

        if (userId != null) {
            session.setUserId(userId);
        }
        if (request.getRoleTitle() != null) {
            session.setRoleTitle(request.getRoleTitle());
        }
        if (request.getInterviewType() != null) {
            session.setInterviewType(request.getInterviewType());
        }
        if (request.getStatus() != null) {
            session.setStatus(request.getStatus());
            if ("Completed".equalsIgnoreCase(request.getStatus()) && session.getEndedAt() == null) {
                session.setEndedAt(LocalDateTime.now());
            }
        }
        if (request.getOverallScore() != null) {
            session.setOverallScore(request.getOverallScore());
        }
        if (request.getOverallFeedback() != null) {
            session.setOverallFeedback(request.getOverallFeedback());
        }
        if (request.getUserRating() != null) {
            session.setUserRating(request.getUserRating());
        }
        if (request.getUserFeedbackText() != null) {
            session.setUserFeedbackText(request.getUserFeedbackText());
        }

        if (request.getResumeId() != null) {
            Resume resume = resumeRepository.findById(request.getResumeId()).orElse(null);
            if (resume != null) {
                if (userId != null && resume.getUserId() == null) {
                    resume.setUserId(userId);
                    resumeRepository.save(resume);
                }
                session.setResume(resume);
            }
        }

        if (request.getJdId() != null) {
            JobDescription jd = jobDescriptionRepository.findById(request.getJdId()).orElse(null);
            if (jd != null) {
                if (userId != null && jd.getUserId() == null) {
                    jd.setUserId(userId);
                    jobDescriptionRepository.save(jd);
                }
                session.setJobDescription(jd);
            }
        }

        session = sessionRepository.save(session);

        if (Boolean.TRUE.equals(request.getReplaceQuestions()) && request.getQuestions() != null) {
            sessionTurnRepository.deleteBySessionId(sessionId);
            for (SessionTurnDto q : request.getQuestions()) {
                SessionTurn turn = SessionTurn.builder()
                        .sessionId(sessionId)
                        .question(q.question())
                        .answer(q.answer())
                        .score(q.score())
                        .strengths(q.strengths())
                        .improvements(q.improvements())
                        .suggestedAnswer(q.suggestedAnswer())
                        .topicTag(q.topicTag())
                        .isDeepDive(q.isDeepDive())
                        .hrRating(q.hrRating())
                        .hrFeedback(q.hrFeedback())
                        .build();
                sessionTurnRepository.save(turn);
            }
        }

        var turns = sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
        return SessionResponse.from(session, turns);
    }

    @Override
    @Transactional(readOnly = true)
    public SessionResponse getSession(String sessionId) {
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        var turns = sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
        return SessionResponse.from(session, turns);
    }

    @Override
    @Transactional(readOnly = true)
    public List<SessionResponse> getSessionsByUser(UUID userId) {
        if (userId == null) {
            return List.of();
        }
        return sessionRepository.findByUserIdOrderByStartedAtDesc(userId)
                .stream()
                .map(session -> SessionResponse.from(session, sessionTurnRepository.findBySessionIdOrderByIdAsc(session.getId())))
                .toList();
    }

    @Override
    @Transactional(readOnly = true)
    public List<SessionResponse> getAllSessions() {
        return sessionRepository.findAllByOrderByStartedAtDesc()
                .stream()
                .map(session -> SessionResponse.from(session, sessionTurnRepository.findBySessionIdOrderByIdAsc(session.getId())))
                .toList();
    }

    @Override
    @Transactional
    public SessionResponse updateSession(String sessionId, UpdateSessionRequest request) {
        Session session = sessionRepository.lockById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        if (request.getRoleTitle() != null || request.getInterviewType() != null || request.getStatus() != null
                || request.getOverallScore() != null || request.getOverallFeedback() != null || request.getEndedAt() != null) {
            requireLegacyWrite(sessionId);
        }

        if (request.getRoleTitle() != null) session.setRoleTitle(request.getRoleTitle());
        if (request.getInterviewType() != null) session.setInterviewType(request.getInterviewType());
        if (request.getStatus() != null) session.setStatus(request.getStatus());
        if (request.getOverallScore() != null) session.setOverallScore(request.getOverallScore());
        if (request.getOverallFeedback() != null) session.setOverallFeedback(request.getOverallFeedback());
        if (request.getUserRating() != null) session.setUserRating(request.getUserRating());
        if (request.getUserFeedbackText() != null) session.setUserFeedbackText(request.getUserFeedbackText());
        if (request.getEndedAt() != null) {
            session.setEndedAt(request.getEndedAt());
        } else if ("Completed".equalsIgnoreCase(request.getStatus()) && session.getEndedAt() == null) {
            session.setEndedAt(LocalDateTime.now());
        }

        session = sessionRepository.save(session);
        var turns = sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
        return SessionResponse.from(session, turns);
    }

    @Override
    @Transactional
    public void deleteSession(String sessionId) {
        if (sessionRepository.findById(sessionId).map(s -> s.getApplicationProfile() != null).orElse(false)) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.CONFLICT,
                    "Application profile attempts are retained as interview history");
        }
        if (!sessionRepository.existsById(sessionId)) {
            throw new ResourceNotFoundException("Session not found with id: " + sessionId);
        }
        sessionTurnRepository.deleteBySessionId(sessionId);
        sessionRepository.deleteById(sessionId);
    }

    @Override
    @Transactional
    public SessionTurn addTurn(String sessionId, SessionTurn turn) {
        sessionRepository.lockById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        requireLegacyWrite(sessionId);
        turn.setSessionId(sessionId);
        return sessionTurnRepository.save(turn);
    }

    private void requireLegacyWrite(String sessionId) {
        if (evidenceRuns.existsById(sessionId) || sessionRepository.findById(sessionId)
                .map(s -> s.getApplicationProfile() != null).orElse(false)) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.CONFLICT, "V2 interview state must be updated through its interview API");
        }
    }

    @Override
    @Transactional(readOnly = true)
    public List<SessionTurn> getSessionTurns(String sessionId) {
        return sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
    }

    @Override
    @Transactional
    public String cloneSession(String sessionId) {
        Session original = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        if (original.getApplicationProfile() != null) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.CONFLICT,
                    "Create a new attempt from the application profile");
        }
        String newSessionId = "session-" + System.currentTimeMillis();
        Session cloned = Session.builder()
                .id(newSessionId)
                .userId(original.getUserId())
                .resume(original.getResume())
                .jobDescription(original.getJobDescription())
                .roleTitle(original.getRoleTitle())
                .interviewType(original.getInterviewType())
                .status("Not started")
                .startedAt(LocalDateTime.now())
                .build();
        sessionRepository.save(cloned);
        return newSessionId;
    }

    @Override
    @Transactional
    public void updateTurnFeedback(String sessionId, Long turnId, Integer hrRating, String hrFeedback) {
        SessionTurn turn = sessionTurnRepository.findById(turnId)
                .orElseThrow(() -> new ResourceNotFoundException("Turn not found with id: " + turnId));
        if (hrRating != null) turn.setHrRating(hrRating);
        if (hrFeedback != null) turn.setHrFeedback(hrFeedback);
        sessionTurnRepository.save(turn);
    }

    @Override
    @Transactional(readOnly = true)
    public Map<String, Object> getRawTexts(UUID resumeId, UUID jdId) {
        String rawCvText = null;
        String cvFilename = null;
        if (resumeId != null) {
            var resumeOpt = resumeRepository.findById(resumeId);
            if (resumeOpt.isPresent()) {
                var r = resumeOpt.get();
                rawCvText = r.getRawText();
                cvFilename = r.getFileName();
            }
        }

        String rawJdText = null;
        String jdFilename = null;
        if (jdId != null) {
            var jdOpt = jobDescriptionRepository.findById(jdId);
            if (jdOpt.isPresent()) {
                var j = jdOpt.get();
                rawJdText = j.getRawText();
                jdFilename = j.getTitle();
            }
        }

        return Map.of(
                "rawCvText", rawCvText != null ? rawCvText : "",
                "rawJdText", rawJdText != null ? rawJdText : "",
                "cvFilename", cvFilename != null ? cvFilename : "",
                "jdFilename", jdFilename != null ? jdFilename : ""
        );
    }
}
