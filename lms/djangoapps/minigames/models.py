from django.db import models


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


