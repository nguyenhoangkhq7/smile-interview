package fit.iuh.modules.skillgap.push;

import com.fasterxml.jackson.databind.ObjectMapper;
import nl.martijndwars.webpush.Encoding;
import nl.martijndwars.webpush.Notification;
import nl.martijndwars.webpush.PushService;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.GeneralSecurityException;
import java.security.Security;
import java.time.Duration;
import java.util.Map;

@Component
public class BrowserPush {
    private final ObjectMapper json;
    private final String publicKey;
    private final Encoder encoder;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();

    public BrowserPush(ObjectMapper json, @Value("${WEB_PUSH_PUBLIC_KEY:}") String publicKey,
                       @Value("${WEB_PUSH_PRIVATE_KEY:}") String privateKey,
                       @Value("${WEB_PUSH_SUBJECT:}") String subject) throws GeneralSecurityException {
        this.json = json;
        this.publicKey = publicKey;
        Security.addProvider(new BouncyCastleProvider());
        encoder = publicKey.isBlank() && privateKey.isBlank() ? null :
                new Encoder(publicKey, privateKey, subject.isBlank() ? null : subject);
    }

    public String publicKey() { return publicKey; }

    static boolean supportedEndpoint(URI uri) {
        String host = uri.getHost();
        if (!"https".equals(uri.getScheme()) || host == null || uri.getRawUserInfo() != null ||
                uri.getFragment() != null || (uri.getPort() != -1 && uri.getPort() != 443)) return false;
        return host.equals("fcm.googleapis.com") || host.equals("updates.push.services.mozilla.com")
                || host.endsWith(".push.services.mozilla.com") || host.equals("web.push.apple.com")
                || host.endsWith(".push.apple.com") || host.endsWith(".notify.windows.com");
    }

    int send(PushDeliveries.Delivery d) throws Exception {
        return http.send(request(d), HttpResponse.BodyHandlers.discarding()).statusCode();
    }

    HttpRequest request(PushDeliveries.Delivery d) throws Exception {
        if (!supportedEndpoint(URI.create(d.endpoint()))) throw new IllegalArgumentException("Invalid push provider");
        byte[] payload = json.writeValueAsBytes(Map.of("sessionId", d.session(), "jobId", d.job().toString()));
        var notification = new Notification(d.endpoint(), d.key(), d.auth(), payload, 86400);
        return encoder.request(notification);
    }

    // Use the library's RFC 8291 encryption and VAPID signing with bounded JDK HTTP timeouts.
    private static class Encoder extends PushService {
        Encoder(String key, String secret, String subject) throws GeneralSecurityException { super(key, secret, subject); }
        HttpRequest request(Notification notification) throws Exception {
            var push = prepareRequest(notification, Encoding.AES128GCM);
            var request = HttpRequest.newBuilder(URI.create(push.getUrl())).timeout(Duration.ofSeconds(15));
            push.getHeaders().forEach(request::header);
            return request.POST(HttpRequest.BodyPublishers.ofByteArray(push.getBody())).build();
        }
    }
}
