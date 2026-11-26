package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

@Component @RequiredArgsConstructor
public class EvidenceJson {
    private final ObjectMapper mapper;

    public JsonNode read(String text) {
        try { return mapper.readTree(text); }
        catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
            throw new IllegalStateException("Invalid persisted interview JSON", ex);
        }
    }

    public JsonNode tree(Object value) { return mapper.valueToTree(value); }

    public String hash(Object value) {
        try {
            byte[] bytes = tree(value).toString().getBytes(StandardCharsets.UTF_8);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
