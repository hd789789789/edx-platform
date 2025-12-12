# StudyGroupStreak Migration Instructions

## Tạo bảng StudyGroupStreak trên server

Để tạo bảng `study_groups_studygroupstreak` trên server, chạy lệnh migration sau:

```bash
python manage.py lms migrate study_groups
```

Hoặc nếu đang ở trong môi trường Django:

```bash
./manage.py lms migrate study_groups
```

Lệnh này sẽ:
1. Tạo bảng `study_groups_studygroupstreak` với các trường:
   - `id`: Primary key
   - `group_id`: Foreign key đến StudyGroup (OneToOne)
   - `streak_length`: Số ngày liên tiếp của chuỗi nhóm
   - `last_day_of_streak`: Ngày cuối cùng của chuỗi
   - `last_updated`: Thời gian cập nhật cuối

2. Tạo các index cần thiết

## Kiểm tra migration đã chạy thành công

Sau khi chạy migration, bạn có thể kiểm tra bằng cách:

```bash
python manage.py lms dbshell
```

Sau đó trong PostgreSQL:

```sql
\d study_groups_studygroupstreak
```

Hoặc kiểm tra trong Django shell:

```python
python manage.py lms shell
```

```python
from lms.djangoapps.study_groups.models import StudyGroupStreak
StudyGroupStreak.objects.all()
```

## Lưu ý

- Migration file: `0002_studygroupstreak.py`
- Bảng sẽ được tạo tự động khi có StudyGroup mới (thông qua `get_or_create`)
- Không cần dữ liệu khởi tạo, bảng sẽ được populate tự động khi API được gọi


