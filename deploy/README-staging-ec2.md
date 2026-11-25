# Hướng dẫn dựng Staging trên 1 EC2 (gồm PostgreSQL 17) & Đo Baseline (Pha 0)

Tài liệu này phục vụ **Pha 0**: dựng sớm môi trường Staging (EC2 + PostgreSQL 17 tự host + Nginx HTTPS + Vercel Preview), kiểm thử phân quyền 2 tài khoản và thu thập số liệu hiệu năng Baseline trước khi tách `ai-service` ở Pha 1.

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

### Khóa EC2 Security Group
- **Inbound cho phép**: `80/tcp` (redirect HTTPS / ACME), `443/tcp` (HTTPS từ Vercel/trình duyệt), và `22/tcp` chỉ mở đúng IP cá nhân (hoặc dùng AWS SSM Session Manager).
- **Tuyệt đối đóng** các cổng `5432`, `8000`, `8001`, `8081` với bên ngoài Internet.

## 2. Cấu hình biến môi trường & khởi chạy Staging

1. Cập nhật tên miền API Staging trong [staging.conf](nginx/staging.conf) (thay `api-staging.example.com`) và cấp chứng chỉ TLS bằng Certbot (`/etc/letsencrypt/live/<domain>/`).
2. Cấu hình `.env`, `backend/.env`, `ai-service/.env` trên EC2, đặc biệt:
   - `APP_CORS_ALLOWED_ORIGINS=https://<your-vercel-staging-domain>`
   - `POSTGRES_PASSWORD=<strong-password>`
   - `JWT_SECRET=<base64-secret-min-32-bytes>`
3. Tải trước trọng số SBERT vào volume `sbert_cache` trước khi chạy thật:
   ```bash
   docker compose -f deploy/docker-compose.staging.yml build
   docker compose -f deploy/docker-compose.staging.yml run --rm --no-deps ai-service \
     python -c "from matching_cv.app.core.config import settings; from matching_cv.app.core.model_loader import model_loader; model_loader.load_model(settings.STAGE3_MODEL_NAME, revision=settings.STAGE3_MODEL_REVISION)"
   docker compose -f deploy/docker-compose.staging.yml up -d
   ```

## 3. Thiết lập Backup PostgreSQL hằng đêm lên S3 & Diễn tập phục hồi

```bash
chmod +x scripts/backup-postgres-s3.sh scripts/restore-postgres-drill.sh
# Chạy thử backup thủ công
BACKUP_S3_BUCKET=<your-bucket> ./scripts/backup-postgres-s3.sh
# Diễn tập phục hồi vào container Postgres trắng
./scripts/restore-postgres-drill.sh s3://<your-bucket>/backups/postgres/<file>.dump
```

Cài cron hằng đêm lúc 02:00:
```cron
0 2 * * * cd /home/ubuntu/smile-interview && BACKUP_S3_BUCKET=<your-bucket> ./scripts/backup-postgres-s3.sh >> /var/log/smile-pg-backup.log 2>&1
```

## 4. Kiểm thử 2 tài khoản & Đo Baseline hiệu năng (trước Pha 1)

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
