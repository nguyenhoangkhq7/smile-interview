package fit.iuh.modules.admin.aipolicy.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFileAttributeView;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;

@Component
public class AiRuntimeKey {
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int SIZE = 32;
    private static final int NONCE = 12;
    private final Path file;
    @Value("${APP_AI_RUNTIME_AUTO_PROVISION:false}")
    private boolean autoProvision;

    @jakarta.annotation.PostConstruct
    void initialize() {
        if (autoProvision) provision();
    }

    public AiRuntimeKey(@Value("${AI_RUNTIME_KEY_FILE:../.runtime/ai-runtime.key}") String path) {
        file = Path.of(path).toAbsolutePath().normalize();
    }

    public boolean authenticate(String header) {
        if (header == null || header.length() != 43) return false;
        try {
            return MessageDigest.isEqual(token().getBytes(StandardCharsets.UTF_8), header.getBytes(StandardCharsets.UTF_8));
        } catch (IllegalStateException ex) {
            return false;
        }
    }

    public String token() {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key(), "HmacSHA256"));
            return encode(mac.doFinal("smile-ai-runtime-client-v1".getBytes(StandardCharsets.UTF_8)));
        } catch (GeneralSecurityException ex) {
            throw new IllegalStateException("Cannot authenticate AI runtime", ex);
        }
    }

    public String seal(String value, String purpose) {
        byte[] nonce = new byte[NONCE];
        RANDOM.nextBytes(nonce);
        byte[] encrypted = cipher(Cipher.ENCRYPT_MODE, nonce, value.getBytes(StandardCharsets.UTF_8), purpose);
        byte[] message = Arrays.copyOf(nonce, NONCE + encrypted.length);
        System.arraycopy(encrypted, 0, message, NONCE, encrypted.length);
        return encode(message);
    }

    public String open(String value, String purpose) {
        byte[] message = Base64.getUrlDecoder().decode(value);
        return new String(cipher(Cipher.DECRYPT_MODE, Arrays.copyOf(message, NONCE),
                Arrays.copyOfRange(message, NONCE, message.length), purpose), StandardCharsets.UTF_8);
    }

    private byte[] cipher(int mode, byte[] nonce, byte[] value, String purpose) {
        try {
            var cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(mode, new SecretKeySpec(key(), "AES"), new GCMParameterSpec(128, nonce));
            cipher.updateAAD(purpose.getBytes(StandardCharsets.UTF_8));
            return cipher.doFinal(value);
        } catch (GeneralSecurityException ex) {
            throw new IllegalStateException("Cannot read or protect AI runtime configuration", ex);
        }
    }

    public synchronized void provision() {
        if (Files.exists(file)) return;
        try {
            Files.createDirectories(file.getParent());
            var permissions = Files.getFileAttributeView(file.getParent(), PosixFileAttributeView.class) == null
                    ? new java.nio.file.attribute.FileAttribute<?>[0]
                    : new java.nio.file.attribute.FileAttribute<?>[]{
                            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------"))};
            var temporary = Files.createTempFile(file.getParent(), "ai-key-", ".tmp", permissions);
            try {
                byte[] value = new byte[SIZE];
                RANDOM.nextBytes(value);
                Files.write(temporary, value);
                try { Files.createLink(file, temporary); }
                catch (FileAlreadyExistsException ignored) { /* Another process already published the complete key. */ }
            } finally {
                Files.deleteIfExists(temporary);
            }
        } catch (IOException ex) {
            throw new IllegalStateException("AI runtime key file is unavailable", ex);
        }
    }

    private byte[] key() {
        try {
            byte[] value = Files.readAllBytes(file);
            if (value.length != SIZE) throw new IOException("Invalid AI runtime key length");
            return value;
        } catch (IOException ex) {
            throw new IllegalStateException("AI runtime key file is unavailable", ex);
        }
    }

    private static String encode(byte[] value) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(value);
    }
}
