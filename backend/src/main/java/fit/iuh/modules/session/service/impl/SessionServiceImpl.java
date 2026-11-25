package fit.iuh.modules.session.service.impl;

import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
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
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Objects;
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
    public SessionResponse createSession(User currentUser, CreateSessionRequest request) {
        User user = requireUser(currentUser);
        UUID userId = user.getId();
        String sessionId = (request.getId() != null && !request.getId().isBlank())
                ? request.getId()
                : "session-" + System.currentTimeMillis();

        log.info("[SessionService] Creating/Upserting session: id={}, userId={}, roleTitle={}", sessionId, userId, request.getRoleTitle());

        Session session = sessionRepository.lockById(sessionId).orElse(null);
        if (session != null && !Objects.equals(session.getUserId(), userId)) {
            throw forbidden("This session belongs to another user");
        }
        requireLegacyWrite(sessionId);
        if (session == null) {
            session = Session.builder()
                    .id(sessionId)
                    .userId(userId)
                    .startedAt(LocalDateTime.now())
                    .status(request.getStatus() != null ? request.getStatus() : "Not started")
                    .build();
        }

        session.setUserId(userId);
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
            Resume resume = resumeRepository.findById(request.getResumeId())
                    .orElseThrow(() -> new ResourceNotFoundException("Resume not found"));
            if (!Objects.equals(resume.getUserId(), userId)) {
                throw forbidden("This resume belongs to another user");
            }
            session.setResume(resume);
        }

        if (request.getJdId() != null) {
            JobDescription jd = jobDescriptionRepository.findById(request.getJdId())
                    .orElseThrow(() -> new ResourceNotFoundException("Job description not found"));
            if (!Objects.equals(jd.getUserId(), userId)) {
                throw forbidden("This job description belongs to another user");
            }
            session.setJobDescription(jd);
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
                        .build();
                sessionTurnRepository.save(turn);
            }
        }

        var turns = sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
        return SessionResponse.from(session, turns);
    }

    @Override
    @Transactional(readOnly = true)
    public SessionResponse getSession(User currentUser, String sessionId) {
        User user = requireUser(currentUser);
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        requireCanRead(session.getUserId(), user, "This session belongs to another user");
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
    @Transactional
    public SessionResponse updateSession(User currentUser, String sessionId, UpdateSessionRequest request) {
        User user = requireUser(currentUser);
        Session session = sessionRepository.lockById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        requireOwner(session.getUserId(), user, "This session belongs to another user");
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
    public void deleteSession(User currentUser, String sessionId) {
        User user = requireUser(currentUser);
        Session session = sessionRepository.lockById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        requireOwner(session.getUserId(), user, "This session belongs to another user");
        if (session.getApplicationProfile() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Application profile attempts are retained as interview history");
        }
        sessionTurnRepository.deleteBySessionId(sessionId);
        sessionRepository.delete(session);
    }

    @Override
    @Transactional
    public SessionTurn addTurn(User currentUser, String sessionId, SessionTurn turn) {
        User user = requireUser(currentUser);
        Session session = sessionRepository.lockById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        requireOwner(session.getUserId(), user, "This session belongs to another user");
        requireLegacyWrite(sessionId);
        turn.setSessionId(sessionId);
        return sessionTurnRepository.save(turn);
    }

    private void requireLegacyWrite(String sessionId) {
        if (evidenceRuns.existsById(sessionId) || sessionRepository.findById(sessionId)
                .map(s -> s.getApplicationProfile() != null).orElse(false)) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT, "V2 interview state must be updated through its interview API");
        }
    }

    @Override
    @Transactional(readOnly = true)
    public List<SessionTurn> getSessionTurns(User currentUser, String sessionId) {
        User user = requireUser(currentUser);
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        requireCanRead(session.getUserId(), user, "This session belongs to another user");
        return sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
    }

    @Override
    @Transactional
    public String cloneSession(User currentUser, String sessionId) {
        User user = requireUser(currentUser);
        Session original = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        requireOwner(original.getUserId(), user, "This session belongs to another user");
        if (original.getApplicationProfile() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Create a new attempt from the application profile");
        }
        if (original.getResume() != null) {
            requireOwner(original.getResume().getUserId(), user, "This resume belongs to another user");
        }
        if (original.getJobDescription() != null) {
            requireOwner(original.getJobDescription().getUserId(), user, "This job description belongs to another user");
        }
        String newSessionId = "session-" + System.currentTimeMillis();
        Session cloned = Session.builder()
                .id(newSessionId)
                .userId(user.getId())
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
    @Transactional(readOnly = true)
    public Map<String, Object> getRawTexts(User currentUser, UUID resumeId, UUID jdId) {
        User user = requireUser(currentUser);
        String rawCvText = null;
        String cvFilename = null;
        if (resumeId != null) {
            Resume r = resumeRepository.findById(resumeId)
                    .orElseThrow(() -> new ResourceNotFoundException("Resume not found with id: " + resumeId));
            requireCanRead(r.getUserId(), user, "This resume belongs to another user");
            rawCvText = r.getRawText();
            cvFilename = r.getFileName();
        }

        String rawJdText = null;
        String jdFilename = null;
        if (jdId != null) {
            JobDescription j = jobDescriptionRepository.findById(jdId)
                    .orElseThrow(() -> new ResourceNotFoundException("Job description not found with id: " + jdId));
            requireCanRead(j.getUserId(), user, "This job description belongs to another user");
            rawJdText = j.getRawText();
            jdFilename = j.getTitle();
        }

        return Map.of(
                "rawCvText", rawCvText != null ? rawCvText : "",
                "rawJdText", rawJdText != null ? rawJdText : "",
                "cvFilename", cvFilename != null ? cvFilename : "",
                "jdFilename", jdFilename != null ? jdFilename : ""
        );
    }

    private User requireUser(User currentUser) {
        if (currentUser == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        return currentUser;
    }

    private void requireOwner(UUID ownerId, User user, String message) {
        if (ownerId == null || !Objects.equals(ownerId, user.getId())) {
            throw forbidden(message);
        }
    }

    private void requireCanRead(UUID ownerId, User user, String message) {
        if (user.getRole() == Role.ADMIN) {
            return;
        }
        requireOwner(ownerId, user, message);
    }

    private ResponseStatusException forbidden(String message) {
        return new ResponseStatusException(HttpStatus.FORBIDDEN, message);
    }
}
