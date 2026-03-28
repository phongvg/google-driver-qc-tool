# Games QC — Kiến trúc & Deploy

## Tổng quan

Hệ thống tự động QC video game session: tải CSV + MP4 từ Google Drive, chạy validators, ghi kết quả vào Google Sheets.

```text
Google Drive
  └─ Root folder
       └─ 2024-01-15/          ← date folder
            └─ SESSION_001/    ← session folder (1 CSV + 1 MP4)

Google Sheets
  └─ Batch 1 ... Batch 60      ← mỗi sheet = 1 batch, mỗi row = 1 session
```

---

## Kiến trúc code

```text
qc/
├── api/app.py               Flask — /health, /check, /auto-check
├── jobs/
│   ├── batch_job.py         Cloud Run Job: QC toàn bộ batch
│   └── index_job.py         Cloud Run Job: build folder index
├── services/
│   ├── qc_service.py        orchestrate download + QC + ghi Sheets
│   └── index_service.py     build/merge/save folder index lên GCS
├── core/
│   ├── qc_core.py           run_qc(), run_csv_only()
│   └── utils.py             combine_status, to_builtin, parse_fraction
├── validators/
│   ├── schema.py            kiểm tra cột, null, kiểu dữ liệu
│   ├── timeline.py          Frame_ID monotonic, timestamp gaps
│   ├── camera_matrix.py     NaN/Inf, last row [0,0,0,1]
│   ├── fov.py               FOV_Deg range, FOV_Axis hợp lệ
│   ├── input_validator.py   keyboard + mouse activity
│   ├── video.py             ffprobe resolution, fps, duration
│   ├── sync.py              delta CSV timestamp vs video duration
│   ├── fps_sync.py          CSV fps vs video fps
│   └── _config.py           CONFIG, REQUIRED_COLUMNS, MATRIX_COLUMNS
└── clients/
    ├── drive_client.py      Google Drive API (retry/backoff)
    └── sheets_client.py     Google Sheets API (batch write)
```

---

## Kiến trúc hạ tầng

```text
Cloud Workflows
  └─ tbrain-games-qc-index     build folder index → lưu GCS
           └─ [poll đến khi xong]
                └─ 6 job song song:
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=1-10
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=11-20
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=21-30
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=31-40
                 ├─ tbrain-games-qc-job  BATCH_NUMBERS=41-50
                 └─ tbrain-games-qc-job  BATCH_NUMBERS=51-60

tbrain-games-qc (Cloud Run Service)
  └─ API: /check, /auto-check, /health
```

Tất cả dùng chung 1 Docker image. Jobs override entrypoint qua `--command python --args -m,jobs.batch_job`.

---

## Hướng giải quyết từng vấn đề

### 1. Folder index — ánh xạ session → Drive folder

**Vấn đề:** Mỗi row trong Sheet chỉ có `session_id`, cần tìm đúng folder Drive chứa CSV + MP4.

**Giải pháp:** Job `index_job` BFS toàn bộ Drive, lưu index dạng versioned JSON lên GCS:

```json
{
  "version": 1,
  "updated_at": "2024-01-15T10:00:00Z",
  "last_full_scan_at": "2024-01-15T10:00:00Z",
  "entries": {
    "SESSION_001": {
      "folder_id": "...",
      "folder_url": "https://drive.google.com/...",
      "parent_date_folder": "2024-01-15",
      "last_seen_at": "2024-01-15T10:00:00Z"
    }
  }
}
```

- **Full scan** (không truyền `DATE_FOLDERS`): replace toàn bộ index, tự heal dữ liệu stale.
- **Incremental scan** (truyền `DATE_FOLDERS`): upsert, phát hiện conflict (cùng session_id ở 2 folder khác nhau).

---

### 2. QC từng session — CSV-first, tránh tải MP4 thừa

**Vấn đề:** MP4 ~300MB/file, nếu CSV đã fail thì tải MP4 lãng phí băng thông + thời gian.

**Giải pháp:** `run_check_internal` tải CSV trước, chạy `run_csv_only()`, chỉ tải MP4 khi CSV pass:

```text
Download CSV (~vài KB)
  └─ run_csv_only(): schema, timeline, matrix, fov, input
       ├─ FAIL → trả kết quả ngay, bỏ qua MP4
       └─ PASS → Download MP4 (~300MB) → run_qc() → video, sync, fps_sync
```

---

### 3. Output contract — chỉ PASS hoặc FAIL

**Vấn đề:** Một số validator trả WARN, consumer (Apps Script) không cần phân biệt WARN vs PASS.

**Giải pháp:** `_build_report()` trong `qc_core.py` convert WARN → PASS và set `had_warnings=True`. Caller đọc `had_warnings` để prefix `[WARN]` vào reason string nếu cần.

---

### 4. Concurrency — xử lý nhiều row song song

**Vấn đề:** Mỗi row cần download 300MB + chạy ffprobe, nếu tuần tự sẽ rất chậm.

**Giải pháp:**

```text
process_batch_sheet()
  └─ ThreadPoolExecutor(max_workers=7)   ← 7 row xử lý song song
       └─ _disk_semaphore(4)             ← tối đa 4 worker được download+process cùng lúc
```

Mỗi thread tự tạo Drive service riêng qua `threading.local()` để tránh race condition.

---

### 5. Ghi Sheets — hybrid flush

**Vấn đề:** Ghi từng row = quá nhiều API call. Ghi cuối batch = mất hết nếu crash.

**Giải pháp:** Tích lũy updates, flush mỗi 10 row. Tối đa mất 9 row nếu crash giữa chừng, đổi lại giảm ~10× số API call.

---

### 6. Workflow — poll thay vì sleep cố định

**Vấn đề:** `sys.sleep(5)` không đủ cho index job, hardcode không linh hoạt.

**Giải pháp:** Workflow poll `executions.get` mỗi 15 giây, kiểm tra `completionTime` và `failedCount` trước khi chạy batch jobs.

---

## Deploy

### Biến

```bash
PROJECT=tbrain-services
REGION=asia-southeast1
REPO=asia-southeast1-docker.pkg.dev/tbrain-services/tbrain-repo
IMAGE=$REPO/games-qc:latest
SA=tbrain-qc-sa@tbrain-services.iam.gserviceaccount.com
BUCKET=tbrain-qc-cache
```

> `SPREADSHEET_ID` và `ROOT_FOLDER_ID` đã có default trong `config.py`.

---

### Bước 1 — Build & push image

```bash
cd qc
docker build -t $IMAGE .
docker push $IMAGE
```

---

### Bước 2 — Deploy Service

```bash
gcloud run deploy tbrain-games-qc \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA \
  --set-env-vars GCS_BUCKET=$BUCKET \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --no-allow-unauthenticated
```

---

### Bước 3 — Deploy Job: index

```bash
gcloud run jobs deploy tbrain-games-qc-index \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA \
  --set-env-vars GCS_BUCKET=$BUCKET \
  --command python \
  --args -m,jobs.index_job \
  --memory 512Mi \
  --cpu 1 \
  --task-timeout 600 \
  --max-retries 0
```

---

### Bước 4 — Deploy Job: batch

```bash
gcloud run jobs deploy tbrain-games-qc-job \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT \
  --service-account $SA \
  --set-env-vars GCS_BUCKET=$BUCKET \
  --command python \
  --args -m,jobs.batch_job \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 3600 \
  --max-retries 0
```

> Memory 2Gi: 7 workers × disk_semaphore=4, mỗi worker giữ ~300MB MP4 trên disk.

---

### Bước 5 — Deploy Workflow

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

## Chạy thủ công

```bash
# Build index toàn bộ Drive
gcloud run jobs execute tbrain-games-qc-index --region $REGION

# Build index chỉ một số ngày
gcloud run jobs execute tbrain-games-qc-index \
  --region $REGION \
  --update-env-vars DATE_FOLDERS=2024-01-15,2024-01-16

# Chạy batch cụ thể
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
| --- | ----- | -------- |
| `GCS_BUCKET` | Bucket lưu folder index | ✓ |
| `SPREADSHEET_ID` | Google Sheet ID (có default) | |
| `ROOT_FOLDER_ID` | Drive root folder ID (có default) | |
| `BATCH_NUMBERS` | Batch cần xử lý, vd `1-10` hoặc `5,7,10` | Job batch |
| `RECHECK_ALL` | Set `all` để ghi đè status cũ | |
| `DATE_FOLDERS` | Giới hạn scan Drive theo ngày | Job index |

---

## Service account roles

| Role | Lý do |
| ---- | ----- |
| `roles/drive.readonly` | Đọc file Drive |
| `roles/spreadsheets.editor` | Ghi kết quả vào Sheets |
| `roles/storage.objectAdmin` | Đọc/ghi folder index trên GCS |
| `roles/run.invoker` | Workflow trigger Cloud Run Jobs |
