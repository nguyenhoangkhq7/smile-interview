package fit.iuh.modules.admin.storage.service;

import fit.iuh.common.storage.ManagedCvRegistry;
import fit.iuh.modules.admin.storage.repository.AdminStorageRepository.ManagedObject;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.S3Exception;
import software.amazon.awssdk.services.s3.model.S3Object;

import java.time.Duration;
import java.util.stream.Stream;

@Component
@RequiredArgsConstructor
class AdminS3Inventory {
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(3);
    private final S3Client s3;

    @Value("${aws.s3.bucket:smile-interview}")
    private String bucket;

    String bucket() {
        return bucket;
    }

    Stream<S3Object> objects(String prefix) {
        var request = ListObjectsV2Request.builder().bucket(bucket).prefix(prefix)
                .overrideConfiguration(config -> config.apiCallTimeout(REQUEST_TIMEOUT)).build();
        return s3.listObjectsV2Paginator(request).contents().stream();
    }

    DeleteStatus delete(ManagedObject object) {
        try {
            // The SDK version in this repository predates the generated If-Match setter.
            s3.deleteObject(DeleteObjectRequest.builder().bucket(bucket)
                    .key(ManagedCvRegistry.PREFIX + object.id())
                    .overrideConfiguration(config -> config.apiCallTimeout(REQUEST_TIMEOUT)
                            .putHeader("If-Match", object.etag())).build());
            return DeleteStatus.DELETED;
        } catch (S3Exception ex) {
            if (ex.statusCode() == 404) return DeleteStatus.MISSING;
            if (ex.statusCode() == 412) return DeleteStatus.CHANGED;
            throw ex;
        }
    }

    enum DeleteStatus { DELETED, MISSING, CHANGED }
}
