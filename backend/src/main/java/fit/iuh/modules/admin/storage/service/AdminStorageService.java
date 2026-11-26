package fit.iuh.modules.admin.storage.service;

import fit.iuh.common.storage.ManagedCvRegistry;
import fit.iuh.modules.admin.storage.dto.AdminStorageDtos;
import fit.iuh.modules.admin.storage.dto.AdminStorageDtos.*;
import fit.iuh.modules.admin.storage.repository.AdminStorageRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.model.S3Object;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class AdminStorageService {
    private static final Duration MINIMUM_AGE = Duration.ofHours(24);
    private static final Path LOCAL_AVATARS = Path.of("uploads", "avatars");

    private final AdminStorageRepository storage;
    private final AdminS3Inventory s3;

    @Value("${app.admin.storage.quota-bytes:0}")
    private long quotaBytes;

    public Overview overview() {
        Instant now = Instant.now();
        List<Segment> segments = new ArrayList<>();
        segments.add(new Segment("postgres", storage.databaseBytes()));
        boolean localMeasured = measureAvatars(segments);
        Inventory inventory = inventory(now.minus(MINIMUM_AGE));
        if (inventory != null) {
            segments.add(new Segment("cv", inventory.cvBytes()));
            segments.add(new Segment("jd", inventory.jdBytes()));
        }
        return new Overview(List.copyOf(segments), segments.stream().mapToLong(Segment::bytes).sum(),
                quotaBytes > 0 ? quotaBytes : null, inventory != null, localMeasured && inventory != null,
                inventory == null ? null : inventory.orphans(), AdminStorageDtos.CLEANUP_BATCH_SIZE, now);
    }

    private Inventory inventory(Instant before) {
        Map<String, String> candidates = storage.orphans(s3.bucket(), before).stream().collect(Collectors.toMap(
                object -> ManagedCvRegistry.PREFIX + object.id(), AdminStorageRepository.ManagedObject::etag));
        try (var objects = s3.objects("resumes/"); var jobDescriptions = s3.objects("jds/")) {
            List<UUID> orphanIds = new ArrayList<>();
            long[] orphanBytes = {0};
            long cvBytes = objects.mapToLong(object -> measureCv(object, candidates, orphanIds, orphanBytes)).sum();
            long jdBytes = jobDescriptions.mapToLong(S3Object::size).sum();
            return new Inventory(cvBytes, jdBytes, new Orphans(List.copyOf(orphanIds), orphanBytes[0], (int) MINIMUM_AGE.toHours()));
        } catch (SdkException ex) {
            log.warn("Could not measure S3 storage ({})", ex.getClass().getSimpleName());
            return null;
        }
    }

    private static long measureCv(S3Object object, Map<String, String> candidates, List<UUID> ids, long[] bytes) {
        String etag = candidates.get(object.key());
        long size = Objects.requireNonNullElse(object.size(), 0L);
        if (etag != null && etag.equals(object.eTag())) {
            ids.add(UUID.fromString(object.key().substring(ManagedCvRegistry.PREFIX.length())));
            bytes[0] += size;
        }
        return size;
    }

    private static boolean measureAvatars(List<Segment> segments) {
        if (Files.notExists(LOCAL_AVATARS, LinkOption.NOFOLLOW_LINKS)) {
            segments.add(new Segment("avatars", 0));
            return true;
        }
        try (var files = Files.find(LOCAL_AVATARS, 1, (path, attributes) -> attributes.isRegularFile())) {
            long bytes = files.mapToLong(AdminStorageService::fileBytes).sum();
            segments.add(new Segment("avatars", bytes));
            return true;
        } catch (IOException | UncheckedIOException ex) {
            log.warn("Could not measure local avatar storage ({})", ex.getClass().getSimpleName());
            return false;
        }
    }

    private static long fileBytes(Path path) {
        try {
            return Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS).size();
        } catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
    }

    public CleanupResult cleanup(List<UUID> ids) {
        Instant before = Instant.now().minus(MINIMUM_AGE);
        var counts = ids.stream().distinct().map(id -> clean(id, before))
                .collect(Collectors.groupingBy(Function.identity(), Collectors.counting()));
        return new CleanupResult(counts.getOrDefault(CleanupStatus.DELETED, 0L).intValue(),
                counts.getOrDefault(CleanupStatus.SKIPPED, 0L).intValue(),
                counts.getOrDefault(CleanupStatus.FAILED, 0L).intValue());
    }

    private CleanupStatus clean(UUID id, Instant before) {
        var candidate = storage.retire(id, s3.bucket(), before);
        if (candidate.isEmpty()) return CleanupStatus.SKIPPED;
        try {
            var status = s3.delete(candidate.get());
            if (status == AdminS3Inventory.DeleteStatus.CHANGED) return CleanupStatus.SKIPPED;
            storage.acknowledgeDeletion(id);
            return status == AdminS3Inventory.DeleteStatus.DELETED ? CleanupStatus.DELETED : CleanupStatus.SKIPPED;
        } catch (SdkException ex) {
            log.warn("Could not clean managed CV {} ({})", id, ex.getClass().getSimpleName());
            return CleanupStatus.FAILED;
        }
    }

    private enum CleanupStatus { DELETED, SKIPPED, FAILED }
    private record Inventory(long cvBytes, long jdBytes, Orphans orphans) {}
}
