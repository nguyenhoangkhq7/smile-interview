package fit.iuh.modules.admin.interviews.service;

import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.DocumentKind;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.DocumentView;
import fit.iuh.modules.admin.interviews.repository.AdminInterviewRepository;
import fit.iuh.modules.admin.interviews.repository.AdminInterviewRepository.DocumentRow;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

@Service
@RequiredArgsConstructor
public class AdminInterviewDocuments {
    private static final int PREVIEW_LENGTH = 1600;
    private static final Path UPLOADS = Path.of("uploads");
    private final AdminInterviewRepository interviews;
    private final S3Client s3;

    @Value("${aws.s3.bucket:smile-interview}") private String bucket;
    @Value("${aws.region:ap-southeast-1}") private String region;

    public DocumentView view(String id, DocumentKind kind, boolean preview) {
        var document = document(id, kind);
        String text = document.text() == null ? "" : document.text().strip();
        return new DocumentView(name(document, kind), preview ? excerpt(text) : text,
                s3Key(document.locator(), kind) != null || localPath(document.locator(), kind) != null);
    }

    public OriginalFile original(String id, DocumentKind kind) {
        var document = document(id, kind);
        String locator = document.locator();
        String key = s3Key(locator, kind);
        if (key != null) return s3File(key, originalName(document, kind, key));
        var local = localPath(locator, kind);
        if (local != null) return new OriginalFile(originalName(document, kind, local.getFileName().toString()), new FileSystemResource(local));
        throw missingFile();
    }

    private DocumentRow document(String id, DocumentKind kind) {
        var documents = interviews.documents(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy phiên phỏng vấn."));
        return kind == DocumentKind.CV ? documents.cv() : documents.jd();
    }

    private OriginalFile s3File(String key, String name) {
        var request = GetObjectRequest.builder().bucket(bucket).key(key)
                .overrideConfiguration(config -> config.apiCallTimeout(Duration.ofSeconds(15))).build();
        try {
            return new OriginalFile(name, new InputStreamResource(s3.getObject(request)));
        } catch (S3Exception ex) {
            if (ex.statusCode() == 404) throw missingFile();
            throw storageUnavailable(ex);
        } catch (SdkException ex) {
            throw storageUnavailable(ex);
        }
    }

    private String s3Key(String locator, DocumentKind kind) {
        if (locator == null) return null;
        String prefix = "https://" + bucket + ".s3." + region + ".amazonaws.com/";
        if (!locator.startsWith(prefix)) return null;
        String key = locator.substring(prefix.length());
        String namespace = directory(kind) + "/";
        if (!key.startsWith(namespace) || key.length() == namespace.length() || key.indexOf('\\') >= 0
                || key.matches("(?s).*/\\.{1,2}(/.*)?")) return null;
        return key;
    }

    private static Path localPath(String locator, DocumentKind kind) {
        String prefix = "/uploads/" + directory(kind) + "/";
        if (locator == null || !locator.startsWith(prefix)) return null;
        String filename = locator.substring(prefix.length());
        if (filename.isBlank() || filename.contains("/") || filename.contains("\\") || filename.contains(":")) return null;
        try {
            Path root = UPLOADS.toRealPath();
            Path path = root.resolve(directory(kind)).resolve(filename).toRealPath();
            return path.getParent().equals(root.resolve(directory(kind))) && Files.isRegularFile(path) ? path : null;
        } catch (IOException | IllegalArgumentException ex) {
            return null;
        }
    }

    private static String excerpt(String text) {
        if (text.length() <= PREVIEW_LENGTH) return text;
        int end = Character.isHighSurrogate(text.charAt(PREVIEW_LENGTH - 1)) ? PREVIEW_LENGTH - 1 : PREVIEW_LENGTH;
        return text.substring(0, end).stripTrailing() + "…";
    }

    private static String directory(DocumentKind kind) { return kind == DocumentKind.CV ? "resumes" : "jds"; }

    private static String name(DocumentRow document, DocumentKind kind) {
        return document.name() == null || document.name().isBlank() ? kind.name() : document.name();
    }

    private static String originalName(DocumentRow document, DocumentKind kind, String key) {
        String filename = key.substring(key.lastIndexOf('/') + 1).replaceFirst("^\\d{10,}_", "");
        if (kind == DocumentKind.CV || filename.isBlank()) filename = name(document, kind);
        return filename.replaceAll("[\\p{Cntrl}/\\\\:\"<>|?*]", "_");
    }

    private static ResponseStatusException missingFile() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Tệp gốc không còn khả dụng.");
    }

    private static ResponseStatusException storageUnavailable(SdkException cause) {
        return new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Không thể đọc tệp gốc từ kho lưu trữ.", cause);
    }

    public record OriginalFile(String name, Resource resource) {}
}
