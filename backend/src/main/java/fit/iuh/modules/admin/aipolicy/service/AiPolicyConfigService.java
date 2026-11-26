package fit.iuh.modules.admin.aipolicy.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.*;
import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.Runtime;
import fit.iuh.modules.admin.aipolicy.repository.AiPolicyRepository;
import fit.iuh.modules.admin.aipolicy.repository.AiPolicyRepository.Stored;
import fit.iuh.modules.admin.audit.dto.AdminAuditDtos.Change;
import fit.iuh.modules.admin.audit.model.AuditAction;
import fit.iuh.modules.admin.audit.service.AdminAuditService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

@Service
@RequiredArgsConstructor
public class AiPolicyConfigService {
    private static final String SECRETS = "smile-ai-db-credentials-v1";
    private static final String TRANSPORT = "smile-ai-runtime-response-v1";
    private final AiPolicyRepository repository;
    private final ObjectMapper json;
    private final AiRuntimeKey key;
    private final AiPolicySources sources;
    private final AdminAuditService audit;

    public View view() {
        var stored = repository.active();
        var defaults = sources.defaults();
        var selected = stored.settings() != null ? settings(stored) : defaults == null ? null : defaults.settings();
        if (selected == null) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI service chưa trả được cấu hình mặc định.");
        var credentials = credentials(stored);
        boolean router = credentials.containsKey("openRouterKey");
        boolean simli = credentials.containsKey("simliKey");
        return new View(stored.revision(), stored.updatedAt(), selected, stored.settings() != null,
                router, simli, router || defaults != null && defaults.openRouterConfigured(),
                simli || defaults != null && defaults.simliConfigured(),
                defaults == null ? List.of() : defaults.skillGapParameters(),
                defaults == null ? null : defaults.embeddingDimension());
    }

    public Policy policy() {
        var selected = settings(repository.active());
        return selected == null ? Policy.defaults() : selected.policy();
    }

    public long revision() { return repository.active().revision(); }

    @Transactional
    public void save(Save request, UUID actor) {
        validate(request.settings());
        var old = repository.active();
        var originalSecrets = credentials(old);
        var secrets = new HashMap<>(originalSecrets);
        var changes = request.credentials();
        if (changes != null) {
            updateKey(secrets, "openRouterKey", changes.openRouterKey(), changes.resetOpenRouterKey());
            updateKey(secrets, "simliKey", changes.simliKey(), changes.resetSimliKey());
        }
        key.provision();
        update(request.revision(), stringify(request.settings()),
                secrets.isEmpty() ? null : key.seal(stringify(secrets), SECRETS), actor);
        var fields = settingChanges(settings(old), request.settings());
        var details = new LinkedHashMap<String, Object>();
        details.put("previousRevision", request.revision());
        details.put("revision", request.revision() + 1);
        for (String keyName : List.of("openRouterKey", "simliKey")) {
            if (!Objects.equals(originalSecrets.get(keyName), secrets.get(keyName))) {
                details.put(keyName + "Change", secrets.containsKey(keyName) ? "REPLACED" : "ENVIRONMENT");
            }
        }
        audit.record(actor, AuditAction.UPDATE_POLICY, request.revision() + 1,
                "Lưu cấu hình AI phiên bản " + (request.revision() + 1) + ".", fields, details);
    }

    @Transactional
    public void reset(Reset request, UUID actor) {
        var old = repository.active();
        update(request.revision(), null, old.credentials(), actor);
        audit.record(actor, AuditAction.RESET_POLICY, request.revision() + 1, "Khôi phục cấu hình AI mặc định.",
                settingChanges(settings(old), null), Map.of("previousRevision", request.revision(),
                        "revision", request.revision() + 1));
    }

    private List<Change> settingChanges(Settings old, Settings updated) {
        JsonNode before = json.valueToTree(old);
        JsonNode after = json.valueToTree(updated);
        var changes = new ArrayList<Change>();
        for (String group : List.of("models", "policy")) {
            JsonNode previous = before.path(group);
            JsonNode current = after.path(group);
            var keys = current.isMissingNode() ? previous.fieldNames() : current.fieldNames();
            keys.forEachRemaining(field -> {
                var oldValue = previous.path(field);
                var newValue = current.path(field);
                if (!oldValue.equals(newValue)) {
                    changes.add(new Change(group + "." + field, oldValue.asText("Mặc định môi trường"),
                            newValue.asText("Mặc định môi trường")));
                }
            });
        }
        return changes;
    }

    public SealedRuntime runtime(String clientToken) {
        if (!key.authenticate(clientToken)) throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        var stored = repository.active();
        return new SealedRuntime(key.seal(stringify(new Runtime(stored.revision(), settings(stored), credentials(stored))), TRANSPORT));
    }

    private void update(long revision, String settings, String credentials, UUID actor) {
        if (repository.update(revision, settings, credentials, actor) == 0) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Cấu hình đã được cập nhật. Hãy tải lại trước khi lưu.");
        }
    }

    private static void validate(Settings settings) {
        var policy = settings.policy();
        if (policy.maxQuestionsPerObjective() > policy.maxQuestions()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Số câu mỗi kỹ năng phải nằm trong tổng số câu.");
        }
        var models = settings.models();
        if (!Set.of(16000, 22050, 24000, 44100, 48000).contains(models.ttsSampleRate())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Tần số lấy mẫu TTS không được hỗ trợ.");
        }
        if (models.ttsModel().replaceFirst("^openrouter/", "").startsWith("heygen/")
                && (!"pcm".equals(models.ttsFormat()) || models.ttsSampleRate() != 44100)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "HeyGen cần PCM ở tần số 44100 Hz.");
        }
        if (policy.voiceEnabled() && policy.simliAvatarEnabled() && !"pcm".equals(models.ttsFormat())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Simli cần định dạng giọng đọc PCM.");
        }
    }

    private static void updateKey(Map<String, String> secrets, String name, String value, boolean reset) {
        if (value != null && (!value.matches("[!-~]{0,512}") || reset && !value.isEmpty())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "API key hoặc lựa chọn thay API key không hợp lệ.");
        }
        if (reset) secrets.remove(name);
        else if (value != null && !value.isEmpty()) secrets.put(name, value);
    }

    private Settings settings(Stored stored) {
        try { return stored.settings() == null ? null : json.readValue(stored.settings(), Settings.class); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("Invalid stored AI configuration", ex); }
    }

    private Map<String, String> credentials(Stored stored) {
        try {
            return stored.credentials() == null ? Map.of() : json.readValue(key.open(stored.credentials(), SECRETS),
                    new TypeReference<Map<String, String>>() {});
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Invalid stored AI credentials");
        }
    }

    private String stringify(Object value) {
        try { return json.writeValueAsString(value); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("Cannot serialize AI configuration"); }
    }
}
