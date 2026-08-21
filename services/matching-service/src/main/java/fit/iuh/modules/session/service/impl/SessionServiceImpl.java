package fit.iuh.modules.session.service.impl;

import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
import fit.iuh.modules.session.repository.ResumeRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.service.SessionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class SessionServiceImpl implements SessionService {

    private final SessionRepository sessionRepository;
    private final ResumeRepository resumeRepository;
    private final JobDescriptionRepository jobDescriptionRepository;

    @Override
    @Transactional
    public SessionResponse createSession(UUID userId, CreateSessionRequest request) {
        String sessionId = (request.getId() != null && !request.getId().isBlank())
                ? request.getId()
                : "session-" + System.currentTimeMillis();

        log.info("[SessionService] Creating/Upserting session: id={}, userId={}, roleTitle={}", sessionId, userId, request.getRoleTitle());

        Session session = sessionRepository.findById(sessionId).orElse(null);
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
        }
        if (request.getAssessmentId() != null) {
            session.setAssessmentId(request.getAssessmentId());
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
        return SessionResponse.from(session);
    }

    @Override
    @Transactional(readOnly = true)
    public SessionResponse getSession(String sessionId) {
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));
        return SessionResponse.from(session);
    }

    @Override
    @Transactional(readOnly = true)
    public List<SessionResponse> getSessionsByUser(UUID userId) {
        if (userId == null) {
            return List.of();
        }
        return sessionRepository.findByUserIdOrderByStartedAtDesc(userId)
                .stream()
                .map(SessionResponse::from)
                .toList();
    }

    @Override
    @Transactional(readOnly = true)
    public List<SessionResponse> getAllSessions() {
        return sessionRepository.findAllByOrderByStartedAtDesc()
                .stream()
                .map(SessionResponse::from)
                .toList();
    }

    @Override
    @Transactional
    public SessionResponse updateSession(String sessionId, UpdateSessionRequest request) {
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found with id: " + sessionId));

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
        return SessionResponse.from(session);
    }

    @Override
    @Transactional
    public void deleteSession(String sessionId) {
        if (!sessionRepository.existsById(sessionId)) {
            throw new ResourceNotFoundException("Session not found with id: " + sessionId);
        }
        sessionRepository.deleteById(sessionId);
    }
}
