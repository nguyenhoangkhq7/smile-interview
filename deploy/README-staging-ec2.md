# Triển khai Smile Interview trên Vercel, EC2 và RDS PostgreSQL

Vercel phục vụ `web-app`. EC2 chạy Nginx, backend và AI service. Backend kết nối RDS PostgreSQL 17 trong cùng VPC, qua TLS có xác minh chứng chỉ và hostname.

## 1. Khởi tạo máy chủ EC2 (`t3a.large` hoặc `t3.large`: 2 vCPU, 8 GB RAM, 40 GB EBS gp3)

### Tạo Swap 4 GB phòng vệ OOM
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-smile-swap.conf
sudo sysctl --system
```

### Mạng và Security Group

- Cho phép `80/tcp` và `443/tcp` vào EC2 cho Nginx. Giới hạn `22/tcp` ở IP quản trị hoặc dùng AWS Systems Manager Session Manager.
- Tạo RDS ở cùng VPC, chọn **Public access = No** và cho Security Group của EC2 truy cập cổng `5432` trên Security Group của RDS. Backend `8081` và AI `8000` dùng mạng Docker. [Hướng dẫn Security Group của RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.RDSSecurityGroups.html)

## 2. Cấu hình và khởi chạy trên EC2

1. Trỏ DNS của API tới EC2, thay `api-staging.example.com` trong [staging.conf](nginx/staging.conf) bằng domain thật và cấp chứng chỉ TLS cho Nginx tại `/etc/letsencrypt/live/<domain>/`.
2. Tạo database trên RDS và cấp quyền cho role của ứng dụng kết nối, tạo và cập nhật các đối tượng trong schema ứng dụng để chạy Flyway. Nếu có dữ liệu từ PostgreSQL tự host, dừng ghi vào DB cũ trong lúc chuyển dữ liệu, tạo bản `pg_dump -Fc` và dùng `pg_restore --no-owner --no-acl --exit-on-error` vào DB RDS trống bằng role của ứng dụng. Giữ volume cũ đến khi xác nhận bảng, dữ liệu và lịch sử Flyway trên RDS.
3. Tạo `.env`, `backend/.env` và `ai-service/.env` từ file mẫu tương ứng.
   - Trong `.env` gốc, đặt `RDS_ENDPOINT` thành hostname RDS, `RDS_DB_NAME` thành tên database và `APP_CORS_ALLOWED_ORIGINS` thành origin HTTPS của frontend trên Vercel.
   - Trong `backend/.env`, đặt `SPRING_DATASOURCE_USERNAME` và `SPRING_DATASOURCE_PASSWORD` của role RDS, cùng `JWT_SECRET` hợp lệ. Với database mới, đặt `ADMIN_BOOTSTRAP_PASSWORD` để đổi mật khẩu admin mặc định. Compose dựng URL JDBC từ `RDS_ENDPOINT` và `RDS_DB_NAME` với `sslmode=verify-full`.
   - Trong `ai-service/.env`, đặt `OPENROUTER_API_KEY` và cấu hình riêng của dịch vụ AI.
4. Tải CA bundle từ AWS trên EC2. Chạy từ thư mục gốc repository. Nếu lưu ở vị trí khác, đặt `RDS_CA_BUNDLE` trong `.env` gốc thành đường dẫn tuyệt đối.

   ```bash
   mkdir -p deploy/certs
   curl --fail --location --output deploy/certs/rds-global-bundle.pem \
     https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
   chmod 644 deploy/certs/rds-global-bundle.pem
   ```

   [Chứng chỉ RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html) · [TLS với RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)

5. Lấy checkpoint `semantic-importance-dependency-gnn-v4` do team huấn luyện, đặt file `paper_aligned_hybrid_gnn_v4_semantic_importance.pt` vào `ai-service/matching_cv/data/checkpoints/paper_aligned_gnn/` và cấp quyền đọc cho container. Nếu dùng thư mục khác, đặt `GNN_CHECKPOINT_DIR` trong `.env` gốc thành đường dẫn tuyệt đối và thay `checkpoint_dir` bên dưới bằng đường dẫn đó. Kiểm tra file bằng [checksum của checkpoint](gnn-v4.sha256) từ thư mục gốc repository.

   ```bash
   repo_dir="$PWD"
   checkpoint_dir="$repo_dir/ai-service/matching_cv/data/checkpoints/paper_aligned_gnn"
   (cd "$checkpoint_dir" && sha256sum --check "$repo_dir/deploy/gnn-v4.sha256")
   ```

   Compose mount thư mục ở chế độ chỉ đọc. AI kiểm tra và nạp trọng số lúc khởi động. Với staging chỉ dùng chế độ chẩn đoán, tạo thư mục mount và đặt `GNN_REQUIRE_CHECKPOINT=false` trong `.env` gốc.
6. Kiểm tra Compose, tải trước trọng số SBERT vào volume `sbert_cache` và khởi chạy. Chạy từ thư mục gốc repository. Backend chạy Flyway và chỉ báo healthy khi truy vấn được database.
   ```bash
   docker compose --env-file .env -f deploy/docker-compose.staging.yml config --quiet
   docker compose --env-file .env -f deploy/docker-compose.staging.yml build
   docker compose --env-file .env -f deploy/docker-compose.staging.yml run --rm --no-deps ai-service \
     python -c "from matching_cv.app.core.config import settings; from matching_cv.app.core.model_loader import model_loader; model_loader.load_model(settings.STAGE3_MODEL_NAME, revision=settings.STAGE3_MODEL_REVISION)"
   docker compose --env-file .env -f deploy/docker-compose.staging.yml up -d --wait
   curl --fail https://api-staging.example.com/actuator/health
   ```

## 3. Triển khai frontend trên Vercel

Chọn Root Directory là `web-app`. Trong môi trường Preview hoặc Production tương ứng, đặt `NEXT_PUBLIC_API_BASE_URL` thành URL HTTPS của API qua Nginx rồi deploy lại. Đặt `APP_CORS_ALLOWED_ORIGINS` trên EC2 thành đúng origin của frontend. Một domain cố định cho staging giúp origin ổn định qua các lần deploy. [Biến môi trường trên Vercel](https://vercel.com/docs/environment-variables)

## 4. Backup và diễn tập khôi phục

Bật automated backups cho RDS với thời hạn lưu phù hợp. Khi diễn tập point-in-time recovery, khôi phục sang một RDS instance riêng và kiểm tra bảng, dữ liệu cùng kết nối backend trước khi dùng endpoint khôi phục. [Hướng dẫn khôi phục RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIT.html)

Nếu team cần thêm bản dump logic trên S3, chạy script từ EC2 có PostgreSQL client 17, AWS CLI và quyền ghi vào bucket. Chuẩn bị `.pgpass` cho role backup với quyền file `0600` và truyền cùng CA bundle đã dùng cho backend. Nếu đã có cron backup PostgreSQL cũ, cập nhật nó sau khi xác minh luồng RDS.

```bash
RDS_ENDPOINT='your-db-instance.region.rds.amazonaws.com' \
RDS_DB_NAME=interview_practice_db RDS_CA_BUNDLE="$PWD/deploy/certs/rds-global-bundle.pem" \
PGUSER=smile_app PGPASSFILE="$HOME/.pgpass" BACKUP_S3_BUCKET='your-backup-bucket' \
  bash scripts/backup-postgres-s3.sh

bash scripts/restore-postgres-drill.sh 's3://your-backup-bucket/backups/postgres/file.dump'
```

Để dùng script với PostgreSQL tự host, truyền `COMPOSE_FILE` trỏ đến cấu hình có service `postgres` cùng tên DB và role nguồn. [Tài liệu `pg_dump`](https://www.postgresql.org/docs/17/app-pgdump.html)

## 5. Kiểm thử 2 tài khoản & đo baseline hiệu năng

```bash
# 1) Kiểm thử phân quyền 2 tài khoản (User A vs User B)
python scripts/staging-baseline-check.py --mode authz \
  --base-url https://api-staging.example.com \
  --email-a usera@example.com --pass-a '<passA>' \
  --email-b userb@example.com --pass-b '<passB>'

# 2) Mở 1 terminal trên EC2 ghi RAM/CPU mỗi 2 giây:
while true; do date -u +%T; docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"; sleep 2; done | tee baseline-docker-stats.log

# 3) Chạy đồng thời phân tích CV/JD + đo độ trễ endpoint Voice (hoặc mở 1 phiên Voice thật song song):
python scripts/staging-baseline-check.py --mode benchmark \
  --base-url https://api-staging.example.com \
  --email-a usera@example.com --pass-a '<passA>' \
  --voice-session-id <active-voice-session-id> \
  --cv-file path/to/sample-cv.pdf --jd-file path/to/sample-jd.pdf \
  --analysis-concurrency 2
```
