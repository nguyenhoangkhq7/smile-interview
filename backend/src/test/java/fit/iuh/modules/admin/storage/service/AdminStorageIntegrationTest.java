package fit.iuh.modules.admin.storage.service;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import fit.iuh.common.service.S3StorageService;
import fit.iuh.common.storage.ManagedCvRegistry;
import fit.iuh.modules.admin.storage.repository.AdminStorageRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.*;

@SpringBootTest
class AdminStorageIntegrationTest {
    private static final String ETAG = "\"55a54008ad1ba589aa210d2629c1df41\"";
    @Autowired JdbcTemplate db;
    @Autowired AdminStorageRepository repository;
    @Autowired ManagedCvRegistry registry;

    @Test
    void snapshotsAndDeletesOnlyVerifiedUnreferencedCvThroughS3Http() throws Exception {
        String bucket = "smile-storage-fixture-" + UUID.randomUUID();
        var old = UUID.randomUUID();
        var linked = UUID.randomUUID();
        var changed = UUID.randomUUID();
        var recent = UUID.randomUUID();
        var external = UUID.randomUUID();
        var linkedResume = UUID.randomUUID();

        var objects = new ConcurrentHashMap<String, String>();
        for (UUID id : List.of(old, linked, changed, recent, external)) {
            objects.put(ManagedCvRegistry.PREFIX + id, ETAG);
        }
        for (UUID id : List.of(old, linked, changed, recent)) {
            int age = id.equals(recent) ? 2 : 48;
            db.update("""
                    INSERT INTO managed_cv_objects(id,bucket,etag,created_at) VALUES (?,?,?,now()-make_interval(hours => ?))
                    """, id, bucket, ETAG, age);
        }
        db.update("INSERT INTO resumes(id,file_name,file_url) VALUES (?,?,?)", linkedResume, "fixture.pdf",
                "https://s3.example/resumes%2Fmanaged%2F" + linked + "?signature=fixture");

        var returnFailure = new AtomicBoolean(false);
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", request -> respond(request, bucket, objects, returnFailure.get()));
        server.start();
        try (S3Client s3 = S3Client.builder().region(Region.AP_SOUTHEAST_1)
                .endpointOverride(URI.create("http://127.0.0.1:" + server.getAddress().getPort()))
                .forcePathStyle(true).credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create("fixture-key", "fixture-secret"))).build()) {
            AdminS3Inventory inventory = new AdminS3Inventory(s3);
            ReflectionTestUtils.setField(inventory, "bucket", bucket);
            AdminStorageService service = new AdminStorageService(repository, inventory);
            var upload = new S3StorageService(s3, registry);
            ReflectionTestUtils.setField(upload, "bucketName", bucket);
            ReflectionTestUtils.setField(upload, "region", "ap-southeast-1");
            String uploaded = upload.uploadFile("resumes/fixture/sample.pdf", new byte[]{1}, "application/pdf");
            UUID uploadId = UUID.fromString(uploaded.substring(uploaded.lastIndexOf('/') + 1));
            assertThat(db.queryForObject("SELECT etag FROM managed_cv_objects WHERE id = ?", String.class, uploadId))
                    .isEqualTo(ETAG);

            var overview = service.overview();
            assertThat(overview.s3Available()).isTrue();
            assertThat(overview.orphans().ids()).containsExactlyInAnyOrder(old, changed);
            assertThat(overview.orphans().bytes()).isEqualTo(256);
            objects.put(ManagedCvRegistry.PREFIX + changed, "\"v2\"");
            var result = service.cleanup(List.of(old, changed, recent, linked, external));
            assertThat(result.deleted()).isEqualTo(1);
            assertThat(result.skipped()).isEqualTo(4);
            assertThat(result.failed()).isZero();
            assertThat(objects.keySet()).doesNotContain(ManagedCvRegistry.PREFIX + old)
                    .contains(ManagedCvRegistry.PREFIX + linked, ManagedCvRegistry.PREFIX + changed);

            assertThatThrownBy(() -> db.update("UPDATE resumes SET file_url = ? WHERE id = ?",
                    "https://s3.example/resumes/managed/" + old, linkedResume))
                    .isInstanceOf(DataIntegrityViolationException.class);

            returnFailure.set(true);
            assertThat(service.overview().s3Available()).isFalse();
            assertThat(service.overview().segments()).anyMatch(segment -> segment.code().equals("postgres"));
        } finally {
            server.stop(0);
            db.update("DELETE FROM resumes WHERE id=?", linkedResume);
            db.update("DELETE FROM managed_cv_objects WHERE bucket=?", bucket);
        }
    }

    private static void respond(HttpExchange request, String bucket, Map<String, String> objects, boolean fail) throws IOException {
        try (request) {
            String path = request.getRequestURI().getPath();
            String prefix = "/" + bucket + "/";
            String key = path.startsWith(prefix) ? path.substring(prefix.length()) : "";
            if ("PUT".equals(request.getRequestMethod())) {
                request.getRequestBody().readAllBytes();
                objects.put(key, ETAG);
                request.getResponseHeaders().set("ETag", ETAG);
                request.sendResponseHeaders(200, -1);
                return;
            }
            if ("DELETE".equals(request.getRequestMethod())) {
                String expected = request.getRequestHeaders().getFirst("If-Match");
                if (expected != null && objects.remove(key, expected)) request.sendResponseHeaders(204, -1);
                else xml(request, 412, "<Error><Code>PreconditionFailed</Code></Error>");
                return;
            }
            if (fail) {
                xml(request, 403, "<Error><Code>AccessDenied</Code></Error>");
                return;
            }
            boolean cv = request.getRequestURI().getRawQuery().contains("resumes");
            String contents = cv ? objects.entrySet().stream().map(entry -> """
                    <Contents><Key>%s</Key><ETag>%s</ETag><Size>128</Size></Contents>
                    """.formatted(entry.getKey(), entry.getValue())).reduce("", String::concat) : "";
            xml(request, 200, "<ListBucketResult xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">"
                    + "<IsTruncated>false</IsTruncated>" + contents + "</ListBucketResult>");
        }
    }

    private static void xml(HttpExchange request, int status, String xml) throws IOException {
        byte[] bytes = xml.getBytes(StandardCharsets.UTF_8);
        request.getResponseHeaders().set("Content-Type", "application/xml");
        request.sendResponseHeaders(status, bytes.length);
        request.getResponseBody().write(bytes);
    }
}
