# QuestionPool API Documentation

## Overview

QuestionPool là một bảng database lưu trữ thông tin về các material/question pools với các trường:

- `mate_id`: Material ID (Primary Key)
- `cat_list`: JSON array các category ID
- `mate_meta`: JSON metadata của material
- `mate_content`: JSON content của material
- `status`: Integer status (0=deleted, 1=active, 2=review, etc.)

## Cài đặt (Local Setup)

### 1. Chạy Migration

```bash
# Cách 1: Sử dụng Django management command
python manage.py lms migrate minigames

# Cách 2: Chạy init script
python lms/djangoapps/minigames/init_question_pool.py
```

### 2. Tạo dữ liệu mẫu (Optional)

```bash
python lms/djangoapps/minigames/sample_question_pool_data.py
```

## API Endpoints

### 1. Lấy tất cả mate_id

```
GET /api/minigames/question-pool/mate-ids/
```

**Response:**
```json
[
    {"mate_id": "math_quiz_001"},
    {"mate_id": "physics_lesson_001"},
    {"mate_id": "chemistry_exam_001"}
]
```

### 2. List/Create Question Pools

```
GET  /api/minigames/question-pool/
POST /api/minigames/question-pool/
```

**Query Parameters (GET):**
- `mate_id`: Filter theo mate_id cụ thể

**POST Body Example:**
```json
{
    "mate_id": "new_material_001",
    "cat_list": ["math", "geometry"],
    "mate_meta": {
        "title": "Geometry Basics",
        "difficulty": "easy",
        "tags": ["math", "geometry"]
    },
    "mate_content": {
        "lessons": [
            {
                "id": "l1",
                "title": "Points and Lines",
                "content": "A point has no dimension..."
            }
        ]
    },
    "status": 1
}
```

### 3. Detail Operations (Get/Update/Delete)

```
GET    /api/minigames/question-pool/{mate_id}/
PUT    /api/minigames/question-pool/{mate_id}/
PATCH  /api/minigames/question-pool/{mate_id}/
DELETE /api/minigames/question-pool/{mate_id}/
```

**Note:** DELETE thực hiện soft delete (set status = 0) thay vì xóa thật.

## Status Codes

- `0`: Deleted (soft delete)
- `1`: Active
- `2`: Under Review
- `3`: Published
- `4`: Archived

## Authentication

Tất cả API endpoints yêu cầu authentication. Sử dụng Bearer token hoặc Session authentication.

## Testing với cURL

```bash
# Lấy tất cả mate_id
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/minigames/question-pool/mate-ids/

# Tạo mới question pool
curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"mate_id":"test_001","cat_list":["test"],"mate_meta":{},"mate_content":{},"status":1}' \
     http://localhost:8000/api/minigames/question-pool/

# Lấy chi tiết
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/minigames/question-pool/test_001/
```

## Database Schema

```sql
CREATE TABLE question_pool (
    mate_id VARCHAR(255) PRIMARY KEY,
    cat_list JSON NOT NULL,
    mate_meta JSON NOT NULL,
    mate_content JSON NOT NULL,
    status INTEGER DEFAULT 1
);
```
