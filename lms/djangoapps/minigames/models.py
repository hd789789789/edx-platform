from django.db import models


class QuestionPool(models.Model):
    """
    Table lưu trữ question pool cho các material.

    Schema:
    {
        "mate_id": "string",           # Material ID (primary key)
        "cat_list": [...],             # JSON array of category IDs
        "mate_meta": {...},            # JSON metadata
        "mate_content": {...},         # JSON content
        "status": 1                    # integer status (0=deleted, 1=active, etc.)
    }
    """

    mate_id = models.CharField(max_length=255, primary_key=True, unique=True)
    cat_list = models.JSONField(help_text="Array of category IDs")
    mate_meta = models.JSONField(help_text="Material metadata")
    mate_content = models.JSONField(help_text="Material content")
    status = models.IntegerField(
        default=1, help_text="Status: 0=deleted, 1=active, 2=review, etc.")

    class Meta:
        db_table = 'question_pool'
        ordering = ['mate_id']
        app_label = 'minigames'

    def __str__(self):
        return f'QuestionPool(mate_id={self.mate_id}, status={self.status})'


class MinigameLog(models.Model):
    """
    Generic log table for custom minigames.

    Schema (the JSON view you yêu cầu):
    {
        "msgid": ...,      # message ID (primary key)
        "msgtype": "...",  # message type (RESULT, EVENT, ...)
        "key": "...",      # hash key (server sẽ generate)
        "tsms": ...,       # timestamp in milliseconds
        "user": "...",     # user id / username ở dạng string
        "payload": {...}   # JSON tuỳ ý cho từng minigame
    }
    """

    msgid = models.BigAutoField(primary_key=True)
    msgtype = models.CharField(max_length=64)
    key = models.CharField(max_length=128, db_index=True)
    tsms = models.BigIntegerField()
    user = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField()

    class Meta:
        db_table = 'minigame_logs'
        ordering = ['-tsms']
        # Giúp Django nhận diện app ngay cả khi settings đặc biệt (như tutor.i18n)
        app_label = 'minigames'

    def __str__(self):
        return f'MinigameLog(msgid={self.msgid}, user={self.user}, msgtype={self.msgtype})'
