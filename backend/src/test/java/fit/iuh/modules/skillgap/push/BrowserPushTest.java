package fit.iuh.modules.skillgap.push;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.auth.entity.User;
import org.bouncycastle.jce.interfaces.ECPublicKey;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import nl.martijndwars.webpush.Utils;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.security.KeyPairGenerator;
import java.security.Security;
import java.security.spec.ECGenParameterSpec;
import java.util.Base64;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@SpringBootTest
@Transactional
class BrowserPushTest {
    @Autowired JdbcTemplate db;
    private final UUID owner = UUID.fromString("a1111111-1111-1111-1111-111111111111");
    private final String endpoint = "https://fcm.googleapis.com/test/" + UUID.randomUUID();

    @Test void signsAndEncryptsBeforeSending() throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        var generator = KeyPairGenerator.getInstance("EC", "BC");
        generator.initialize(new ECGenParameterSpec("secp256r1"));
        var pair = generator.generateKeyPair();
        var base64 = Base64.getUrlEncoder().withoutPadding();
        var publicKey = base64.encodeToString(Utils.encode((ECPublicKey) pair.getPublic()));
        var privateKey = base64.encodeToString(Utils.encode((org.bouncycastle.jce.interfaces.ECPrivateKey) pair.getPrivate()));
        var sender = new BrowserPush(new ObjectMapper(), publicKey, privateKey, "mailto:test@example.org");
        var delivery = new PushDeliveries.Delivery(UUID.randomUUID(), UUID.randomUUID(), 1, "session",
                endpoint, publicKey, base64.encodeToString(new byte[16]));
        var http = sender.request(delivery);
        assertThat(http.headers().firstValue("Authorization").orElseThrow()).startsWith("vapid ");
        assertThat(http.headers().firstValue("Content-Encoding")).contains("aes128gcm");
        assertThat(http.bodyPublisher().orElseThrow().contentLength()).isGreaterThan(50);
        assertThatCode(sender::prepareTestNotification).doesNotThrowAnyException();
    }

    @Test void optInAfterCompletionIsIdempotentAndExpiredDevicesAreRemoved() throws Exception {
        String session = UUID.randomUUID().toString();
        UUID job = UUID.randomUUID();
        db.update("INSERT INTO sessions(id,user_id) VALUES (?,?)", session, owner);
        db.update("INSERT INTO skill_gap_jobs(id,session_id,owner_id,input_key,status) VALUES (?,?,?,'hash','SUCCEEDED')",
                job, session, owner);
        var sender = mock(BrowserPush.class);
        when(sender.publicKey()).thenReturn("configured");
        var subscriptions = new PushSubscriptions(db, sender);
        var generator = KeyPairGenerator.getInstance("EC", "BC");
        generator.initialize(new ECGenParameterSpec("secp256r1"));
        var encoder = Base64.getUrlEncoder().withoutPadding();
        var keys = new PushSubscriptions.Keys(encoder.encodeToString(Utils.encode((ECPublicKey)generator.generateKeyPair().getPublic())),
                encoder.encodeToString(new byte[16]));
        var device = new PushSubscriptions.Subscription(endpoint, keys, job);
        var user = User.builder().id(owner).build();
        assertThatThrownBy(() -> subscriptions.enable(User.builder().id(UUID.randomUUID()).build(), device))
                .isInstanceOf(ResourceNotFoundException.class);
        subscriptions.enable(user, device);
        subscriptions.enable(user, device);
        assertThat(db.queryForObject("SELECT count(*) FROM analysis_push_deliveries WHERE job_id=?", Integer.class, job)).isOne();
        when(sender.send(any())).thenReturn(503, 410);
        var deliveries = new PushDeliveries(db, sender);
        deliveries.deliver();
        assertThat(db.queryForObject("SELECT available_at>now() FROM analysis_push_deliveries WHERE job_id=?", Boolean.class, job)).isTrue();
        db.update("UPDATE analysis_push_deliveries SET available_at=now() WHERE job_id=?", job);
        deliveries.deliver();
        assertThat(subscriptions.status(user, new PushSubscriptions.Endpoint(endpoint))).isFalse();
    }
}
