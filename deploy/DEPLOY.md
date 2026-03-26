# Deploy Guide — Games QC

## Kiến trúc

```
Cloud Workflows
  └─ Cloud Run Job: tbrain-games-qc-index   (build folder index → GCS)
       └─ [poll đến khi xong]
            └─ 4 job song song:
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=1-10
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=11-20
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=21-30
                 └─ tbrain-games-qc-job  BATCH_NUMBERS=31-40

Cloud Run Service: tbrain-games-qc   (API — /check, /auto-check, /health)
```

Tất cả dùng chung 1 image. Job override `CMD` qua `--command python --args job.py`.

---

## Biến

```bash
PROJECT=tbrain-services
REGION=asia-southeast1
REPO=asia-southeast1-docker.pkg.dev/tbrain-services/tbrain-repo
IMAGE=$REPO/games-qc:latest
SA=tbrain-qc-sa@tbrain-services.iam.gserviceaccount.com
BUCKET=tbrain-qc-cache
SHEET_ID=<spreadsheet_id>
```

---

## Bước 1 — Build & push image

```bash
cd qc
docker build -t $IMAGE .
docker push $IMAGE
```

---

## Bước 2 — Deploy Service (API)

```bash
gcloud run deploy tbrain-games-qc \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA \
  --set-env-vars GCS_BUCKET=$BUCKET,SPREADSHEET_ID=$SHEET_ID \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --no-allow-unauthenticated
```

---

## Bước 3 — Deploy Job: index

```bash
gcloud run jobs deploy tbrain-games-qc-index \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA \
  --set-env-vars GCS_BUCKET=$BUCKET,SPREADSHEET_ID=$SHEET_ID \
  --command python \
  --args -m,jobs.index_job \
  --memory 512Mi \
  --cpu 1 \
  --task-timeout 600 \
  --max-retries 0
```

---

## Bước 4 — Deploy Job: batch

```bash
gcloud run jobs deploy tbrain-games-qc-job \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA \
  --set-env-vars GCS_BUCKET=$BUCKET,SPREADSHEET_ID=$SHEET_ID \
  --command python \
  --args -m,jobs.batch_job \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 3600 \
  --max-retries 0
```

Workflow trigger job này 4 lần song song, mỗi lần override `BATCH_NUMBERS` khác nhau.

---

## Bước 5 — Deploy Workflow

```bash
gcloud workflows deploy tbrain-games-qc-workflow \
  --source deploy/workflow.yaml \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA
```

---

## Chạy

```bash
# Chạy bình thường (bỏ qua row đã có status)
gcloud workflows run tbrain-games-qc-workflow \
  --region $REGION \
  --data='{"recheck_all": ""}'

# Recheck toàn bộ (ghi đè status cũ)
gcloud workflows run tbrain-games-qc-workflow \
  --region $REGION \
  --data='{"recheck_all": "all"}'
```

---

## Chạy thủ công từng job

```bash
# Chỉ build index
gcloud run jobs execute tbrain-games-qc-index --region $REGION

# Chỉ chạy batch cụ thể
gcloud run jobs execute tbrain-games-qc-job \
  --region $REGION \
  --update-env-vars BATCH_NUMBERS=1-10

# Test local
python -m jobs.index_job
python -m jobs.batch_job
```

---

## Env vars

| Tên | Mô tả | Bắt buộc |
|-----|-------|----------|
| `GCS_BUCKET` | Bucket lưu folder index | ✓ |
| `SPREADSHEET_ID` | Google Sheet ID | ✓ |
| `BATCH_NUMBERS` | Range batch xử lý, vd `1-10` hoặc `5,7,10` | Job batch |
| `RECHECK_ALL` | Set `all` để ghi đè status cũ | |
| `DATE_FOLDERS` | Giới hạn scan Drive theo ngày, vd `2024-01-15,2024-01-16` | Job index |

---

## Lưu ý

- **Memory job batch**: 7 workers × disk_semaphore=4, mỗi worker download ~300MB MP4 → cần `2Gi`.
- **`--max-retries 0`**: job thất bại không tự retry để tránh ghi đè kết quả đang xử lý.
- **Service account** cần roles: `Drive Reader`, `Sheets Editor`, `Storage Object Admin`, `Cloud Run Invoker`.
