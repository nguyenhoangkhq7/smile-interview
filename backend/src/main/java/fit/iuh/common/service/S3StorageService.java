package fit.iuh.common.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

@Slf4j
@Service
@RequiredArgsConstructor
public class S3StorageService {

    private final S3Client s3Client;

    @Value("${aws.s3.bucket:smile-interview}")
    private String bucketName;

    @Value("${aws.region:ap-southeast-1}")
    private String region;

    /**
     * Uploads file content to the configured Amazon S3 bucket.
     *
     * @param key S3 object key (e.g. "cvs/session-123.pdf" or "audio/turn-1.webm")
     * @param content File bytes
     * @param contentType MIME type of the file
     * @return Public S3 HTTPS URL of the uploaded file
     */
    public String uploadFile(String key, byte[] content, String contentType) {
        log.info("[S3StorageService] Uploading file to bucket={}, key={}, size={} bytes", bucketName, key, content.length);
        PutObjectRequest putRequest = PutObjectRequest.builder()
                .bucket(bucketName)
                .key(key)
                .contentType(contentType != null ? contentType : "application/octet-stream")
                .build();

        s3Client.putObject(putRequest, RequestBody.fromBytes(content));
        String fileUrl = String.format("https://%s.s3.%s.amazonaws.com/%s", bucketName, region, key);
        log.info("[S3StorageService] Successfully uploaded to: {}", fileUrl);
        return fileUrl;
    }
}
