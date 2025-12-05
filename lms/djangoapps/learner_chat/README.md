# Learner Chat Module

Module chat cho người học trong OpenEdX, cho phép học viên chat real-time với nhau trong các khóa học.

## Tính năng

- ✅ Chat real-time giữa những người học (sử dụng polling)
- ✅ 3 loại phòng chat: Chung, Hỏi & Đáp, Kỹ thuật
- ✅ Lưu trữ tin nhắn trong database
- ✅ Quyền xóa tin nhắn: Admin có thể xóa bất kỳ tin nhắn nào, người dùng chỉ có thể xóa tin nhắn của mình
- ✅ Emoji picker
- ✅ @mention người dùng
- ✅ Giao diện đẹp, hỗ trợ dark mode
- ✅ Tích hợp vào learner-dashboard

## Cài đặt

### 1. Thêm app vào INSTALLED_APPS

Thêm `'lms.djangoapps.learner_chat'` vào `INSTALLED_APPS` trong file cấu hình Django (thường là `lms/envs/common.py` hoặc `lms/envs/production.py`):

```python
INSTALLED_APPS = [
    # ... các app khác
    'lms.djangoapps.learner_chat',
]
```

### 2. Chạy migrations

```bash
python manage.py makemigrations learner_chat
python manage.py migrate learner_chat
```

### 3. Cấu hình URLs

URLs đã được tự động thêm vào `lms/urls.py`:

```python
path('api/learner_chat/', include('lms.djangoapps.learner_chat.urls')),
```

## API Endpoints

### Lấy danh sách tin nhắn

```
GET /api/learner_chat/{course_key}/{chat_type}/messages/
```

**Parameters:**
- `course_key`: Course key (ví dụ: `course-v1:edX+DemoX+Demo_Course`)
- `chat_type`: Loại chat (`general`, `qa`, hoặc `technical`)

**Response:**
```json
{
  "room_id": 1,
  "course_id": "course-v1:edX+DemoX+Demo_Course",
  "chat_type": "general",
  "messages": [
    {
      "id": 1,
      "user": {
        "id": 1,
        "username": "student1",
        "display_name": "Student One"
      },
      "message": "Hello everyone!",
      "mentions": [],
      "is_deleted": false,
      "created_at": "2025-01-20T10:00:00Z",
      "can_delete": true
    }
  ]
}
```

### Gửi tin nhắn

```
POST /api/learner_chat/{course_key}/{chat_type}/messages/
```

**Body:**
```json
{
  "message": "Hello @student2, how are you? 😊"
}
```

**Response:**
```json
{
  "id": 2,
  "user": {
    "id": 1,
    "username": "student1",
    "display_name": "Student One"
  },
  "message": "Hello @student2, how are you? 😊",
  "mentions": [
    {
      "id": 2,
      "username": "student2",
      "display_name": "Student Two"
    }
  ],
  "is_deleted": false,
  "created_at": "2025-01-20T10:05:00Z",
  "can_delete": true
}
```

### Xóa tin nhắn

```
DELETE /api/learner_chat/{course_key}/{chat_type}/messages/{message_id}/
```

**Response:**
```json
{
  "success": true,
  "message": "Message deleted"
}
```

## Models

### ChatRoom

Đại diện cho một phòng chat trong một khóa học.

- `course_id`: CourseKey của khóa học
- `chat_type`: Loại chat (`general`, `qa`, `technical`)
- `created_at`, `updated_at`: Timestamps

### ChatMessage

Đại diện cho một tin nhắn trong phòng chat.

- `room`: ForeignKey đến ChatRoom
- `user`: ForeignKey đến User (người gửi)
- `message`: Nội dung tin nhắn
- `mentions`: ManyToMany đến User (những người được mention)
- `is_deleted`: Boolean, đánh dấu tin nhắn đã bị xóa
- `deleted_by`: ForeignKey đến User (người xóa)
- `deleted_at`: Timestamp khi xóa
- `created_at`, `updated_at`: Timestamps

## Frontend Component

Component React `LearnerChat` đã được tích hợp vào `frontend-app-learner-dashboard`.

### Sử dụng

Component tự động hiển thị trong learner dashboard khi có khóa học được đăng ký. Người dùng có thể:

1. Click vào nút chat ở góc dưới bên phải để mở chat
2. Chọn tab chat (Chung, Hỏi & Đáp, Kỹ thuật)
3. Gửi tin nhắn với emoji và @mention
4. Xóa tin nhắn (nếu có quyền)

### Props

```javascript
<LearnerChat
  courseId="course-v1:edX+DemoX+Demo_Course"
  isOpen={true}
  onClose={() => setIsOpen(false)}
/>
```

## Permissions

- **Người dùng thường**: Chỉ có thể xóa tin nhắn của chính mình
- **Admin/Staff**: Có thể xóa bất kỳ tin nhắn nào

## Real-time Updates

Hiện tại sử dụng polling (mỗi 3 giây) để cập nhật tin nhắn mới. Có thể nâng cấp lên WebSocket (Django Channels) trong tương lai để có real-time tốt hơn.

## Dark Mode

Component tự động hỗ trợ dark mode dựa trên theme của hệ thống.

## Troubleshooting

### Chat không hiển thị

1. Kiểm tra xem app đã được thêm vào `INSTALLED_APPS` chưa
2. Kiểm tra migrations đã chạy chưa
3. Kiểm tra console browser để xem có lỗi API không

### Không thể gửi tin nhắn

1. Kiểm tra user đã đăng ký khóa học chưa
2. Kiểm tra CSRF token
3. Kiểm tra permissions trong backend

## Tương lai

- [ ] Nâng cấp lên WebSocket (Django Channels) cho real-time tốt hơn
- [ ] Thêm file upload
- [ ] Thêm notification khi có tin nhắn mới
- [ ] Thêm search trong chat
- [ ] Thêm typing indicator


