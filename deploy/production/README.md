# Phát hành production từ main

Nhóm merge nhánh tính năng vào `develop` qua PR, sau đó mở PR từ `develop` vào `main` để phát hành. GitHub Actions kiểm thử cùng Git SHA, build và quét image, đẩy image lên ECR, chuẩn bị frontend trên Vercel, rồi dùng SSM Run Command để cập nhật EC2. API, CORS và phép suy luận GNN phải đạt trước khi chuyển domain Vercel. Mỗi release dùng Compose project `smile-production`. Trên một EC2, API có thể gián đoạn trong lúc thay container.

## 1. Bootstrap qua AWS Console

1. Chọn cùng một AWS region cho workload. Tạo VPC hoặc dùng VPC hiện có với một public subnet cho EC2, hai private subnet ở hai AZ cho RDS DB subnet group. Tạo RDS PostgreSQL 17 Single-AZ, mã hóa storage, Public access = No, automated backups 7 ngày. Security group RDS nhận TCP 5432 từ security group EC2. Tạo database và app role sở hữu schema để Flyway chạy được.
2. Tạo EC2 Ubuntu 24.04 x86_64, 2 vCPU, 8 GiB RAM, EBS gp3 mã hóa (bắt đầu với 40 GiB, theo dõi dung lượng cache và image). Gắn Elastic IP. Cho phép inbound TCP 80/443, quản trị qua Session Manager. Cho phép outbound HTTPS để tải image, trọng số SBERT và gọi dịch vụ ngoài. Trỏ bản ghi A của API về Elastic IP.
3. Tạo hai private ECR repositories `smile/backend`, `smile/ai-service`, bật immutable tags. Tạo một S3 bucket private, Block Public Access, bật versioning và mã hóa. Giữ các image digest, bundle và phiên bản model cần cho cửa sổ rollback. Dùng bucket riêng cho file upload của ứng dụng nếu bật tính năng đó.
4. Trong S3 Console, upload checkpoint do nhóm train vào `models/<sha256>/<filename>`. Lấy cả SHA-256 và tên file từ [gnn-v4.sha256](../gnn-v4.sha256). EC2 kiểm tra byte thực tế và mount file read-only.
5. Trong Parameter Store, tạo hai **SecureString** nhiều dòng. Mỗi dòng có dạng `KEY=value`, không có dấu nháy bao giá trị. `/smile/production/backend` chứa ít nhất `SPRING_DATASOURCE_USERNAME`, `SPRING_DATASOURCE_PASSWORD`, `JWT_SECRET` (sinh bằng `openssl rand -base64 48`) và `ADMIN_BOOTSTRAP_PASSWORD` cho DB mới. `/smile/production/ai-service` chứa `OPENROUTER_API_KEY` cùng cấu hình AI của nhóm. Xem hai file `.env.example` tương ứng để bổ sung các tích hợp mình dùng.
6. Gắn instance profile có `AmazonSSMManagedInstanceCore` cho EC2. Cấp thêm các quyền trong bảng dưới. Xác nhận máy hiển thị **Online** trong Systems Manager Fleet Manager.

| Principal | Quyền và phạm vi |
| --- | --- |
| EC2 instance role | `ecr:GetAuthorizationToken` trên `*`. `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchCheckLayerAvailability` trên hai repo. `s3:GetObject` trên `releases/*`, `models/*`. `ssm:GetParameter` trên đúng hai SecureString. Nếu dùng customer-managed KMS key, cấp `kms:Decrypt` tương ứng. |
| GitHub release role | `ecr:GetAuthorizationToken` trên `*`. `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`, `ecr:BatchGetImage`, `ecr:DescribeImages` trên hai repo. `s3:PutObject` trên `releases/*` và `production/state.json`, `s3:GetObject` trên state, `s3:ListBucket` với prefix `production/state.json`. Nếu dùng SSE-KMS, cấp quyền key cho đọc/ghi tương ứng. |
| GitHub release role, SSM | `ssm:SendCommand` trên ARN của đúng EC2 instance và document `arn:aws:ssm:REGION::document/AWS-RunShellScript`. `ssm:ListCommandInvocations` trên `*`. Quyền gửi shell command tương đương quyền root trên máy đích. Bảo vệ thay đổi workflow và script qua review trên main. |

Tạo IAM OIDC provider `token.actions.githubusercontent.com`, audience `sts.amazonaws.com`. Release role cho phép `sts:AssumeRoleWithWebIdentity` từ provider này, với hai điều kiện **StringEquals** cho `token.actions.githubusercontent.com:aud = sts.amazonaws.com` và `token.actions.githubusercontent.com:sub = repo:nguyenhoangkhq7/smile-interview:environment:production`. Đặt maximum session duration của role thành ít nhất 3 giờ. [GitHub OIDC cho AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)

## 2. Chuẩn bị EC2 và HTTPS

Cài Docker Engine, Docker Compose plugin **v2.30 trở lên** (dùng env file ở định dạng raw), AWS CLI v2, jq, curl, util-linux và Certbot. Kiểm tra `sudo aws sts get-caller-identity`, `sudo docker compose version` và dung lượng EBS. Bật Docker khi khởi động lại. [Docker Engine trên Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

Trong Session Manager vào root shell bằng `sudo -i`, tạo `/etc/smile` và ghi file `/etc/smile/production.conf` với quyền `0600`. Thay các giá trị ví dụ bằng thông tin của nhóm.

```bash
AWS_DEFAULT_REGION=ap-southeast-1
RELEASE_BUCKET=my-private-release-bucket
API_HOST=api.example.com
APP_CORS_ALLOWED_ORIGINS=https://my-app.vercel.app
RDS_ENDPOINT=mydb.example.ap-southeast-1.rds.amazonaws.com
RDS_DB_NAME=interview_practice_db
```

Sau khi DNS có hiệu lực, chạy một lần trên máy mới. Container bootstrap phục vụ ACME challenge qua HTTP cho tới khi cấp được chứng chỉ.

```bash
set -e
source /etc/smile/production.conf
install -d -m 755 /etc/smile /var/www/certbot
curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o /etc/smile/rds-global-bundle.pem
chmod 644 /etc/smile/rds-global-bundle.pem
docker run -d --name smile-acme-bootstrap -p 80:80 \
  -v /var/www/certbot:/usr/share/nginx/html:ro nginx:1.30.8-alpine
certbot certonly --webroot -w /var/www/certbot -d "$API_HOST"
docker rm -f smile-acme-bootstrap
install -d /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/smile-nginx <<'HOOK'
#!/bin/sh
set -eu
id=$(docker ps -q --filter label=com.docker.compose.project=smile-production --filter label=com.docker.compose.service=nginx)
test -n "$id" && docker exec "$id" nginx -s reload
HOOK
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/smile-nginx
```

Sau release đầu, chạy `certbot renew --dry-run` và kiểm tra timer gia hạn. CA của RDS được mount vào backend để JDBC kết nối với `sslmode=verify-full`.

## 3. Cấu hình GitHub và Vercel

- Tạo project Vercel có Root Directory `web-app`, framework Next.js và biến Production `NEXT_PUBLIC_API_BASE_URL=https://<API_HOST>`. Gắn domain frontend ổn định. Dùng CLI làm đường phát hành production duy nhất. Nếu đã import repo, ngắt Git Integration trước khi bật CD để tránh Vercel tự chuyển domain khi push. Tạo token cho team/project sở hữu deployment.
- Trong GitHub tạo Environment `production`, restrict deployment branches tới `main`. Environment secret là `VERCEL_TOKEN`. Environment variables gồm `AWS_REGION`, `AWS_RELEASE_ROLE_ARN`, `EC2_INSTANCE_ID`, `RELEASE_BUCKET`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `API_ORIGIN` và `WEB_ORIGIN`. Hai origin là URL HTTPS chính xác, không có dấu slash cuối. Dùng cùng region, bucket, API hostname và web origin đã cấu hình trên máy.
- Giữ **repository variable** `PRODUCTION_CD_ENABLED=false` khi bootstrap. Merge các thay đổi CD, JWT và bootstrap admin qua PR. Bật branch protection cho `main`, yêu cầu review và các check backend, web và AI/deploy của PR. Chọn các check từ lần PR thực sự chạy.
- Trong **Actions → Production release → Run workflow**, chọn `main`, để trống `rollback_sha`. Kiểm tra summary chứa SHA, hai image digest, Vercel deployment ID và checksum GNN. Đăng nhập tài khoản admin trên domain frontend, thực hiện một lượt matching và upload file thử. Sau khi đổi mật khẩu admin theo quy trình của nhóm, bỏ password bootstrap khỏi Parameter Store để release tiếp theo lấy cấu hình mới.

## 4. Diễn tập và vận hành

- **Checksum sai** — Trên hạ tầng mới trước khi mở cho người dùng, thử lần chạy đầu với file test sai ở object key đã định. SSM `prepare` phải fail trước khi đổi container. Khôi phục đúng S3 object version, chạy lại và kiểm tra checksum thành công. Sau khi model đã được cache, EC2 kiểm tra file local theo checksum mỗi lần deploy.
- **API lỗi sau cập nhật** — Sau release đầu thành công, trước khi nhận traffic thật, tạo PR diễn tập cho smoke GNN trả exit code 1 trong candidate. Merge và chạy thủ công. Kiểm tra run báo lỗi, API chạy lại image digest trước, file upload thử còn đọc được và domain web giữ nguyên deployment ID. Revert commit diễn tập, deploy lại. Khi đạt, đặt **repository variable** `PRODUCTION_CD_ENABLED=true`.
- **Rollback** — Chạy lại workflow trên `main`, nhập đủ 40 ký tự Git SHA của release thành công. Pipeline lấy artifact và Vercel deployment đã lưu cho SHA đó, chuẩn bị lại EC2, kiểm tra API rồi chuyển frontend. Rollback giữ volume uploads, cache SBERT và dữ liệu RDS. Thiết kế migration theo expand/contract để backend cũ đọc được schema mới. Với migration phá vỡ tương thích, lập lịch bảo trì và kiểm thử phục hồi RDS riêng trước khi merge.
- **Điều tra lỗi** — Xem command ID trong Actions, rồi mở Systems Manager → Run Command → Command history. Trên EC2 dùng `docker ps --filter label=com.docker.compose.project=smile-production` và `docker logs --tail 150 <container>`. State chính thức nằm ở `s3://<bucket>/production/state.json`. Nếu job bị hủy hoặc mất kết nối giữa chừng, chờ lệnh SSM cuối kết thúc, kiểm tra state và alias Vercel, rồi chạy rollback về `current.sha`. Với lần đầu chưa có current, sửa nguyên nhân rồi chạy thủ công lại.
- **Lưu giữ** — Bật theo dõi dung lượng EBS và RDS, lưu bản backup RDS theo thời hạn đã chọn. Giữ thư mục của release hiện tại và bản dùng để phục hồi trong `/var/lib/smile/releases` với quyền root vì chúng chứa env file. Giữ artifact S3, ECR, Vercel và checkpoint trong suốt thời gian cần rollback. Khôi phục dữ liệu RDS bằng point-in-time recovery sang instance riêng khi cần.
